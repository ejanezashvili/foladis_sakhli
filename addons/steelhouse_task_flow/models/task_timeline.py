"""Data for the "Timeline" view: tasks as bars from start (work start / creation) to the deadline."""
from datetime import date, timedelta

from odoo import api, fields, models

CLOSED = ('1_done', '1_canceled')
MAX_TASKS = 1500


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_tl_day(self, dt):
        return fields.Datetime.context_timestamp(self, dt).date() if dt else False

    def _sh_tl_item(self, today):
        """One bar. Dates are 'YYYY-MM-DD' in the user's time zone."""
        self.ensure_one()
        start = self.sh_work_start or self._sh_tl_day(self.create_date)
        deadline = self._sh_tl_day(self.date_deadline)
        closed = self.state in CLOSED
        closed_on = self._sh_tl_day(self.date_last_stage_update) if closed else False
        end = deadline or closed_on or today
        if end < start:
            start = end
        kind = self.stage_id.sh_kind or ('done' if self.state == '1_done' else 'new')
        if self.state == '1_canceled':
            kind = 'cancelled'
        user = self.sh_responsible_id or self.user_ids[:1]
        return {
            'id': self.id,
            'number': self.sh_number or '',
            'name': self.name,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'deadline': deadline and deadline.isoformat() or '',
            'open_end': not deadline and not closed,      # no deadline yet: bar runs up to today
            # same rule as the red cards / filter: the deadline moment has passed
            'overdue': bool(self.date_deadline and not closed and self.date_deadline < fields.Datetime.now()),
            'closed_on': closed_on and closed_on.isoformat() or '',
            'kind': kind,
            'stage': self.stage_id.name or '',
            'progress': self.sh_progress,
            'priority': self.priority or '0',
            'department': self.project_id.name or '',
            'project': self.sh_project_id.name or '',
            'users': ', '.join(self.user_ids.mapped('name')),
            'responsible': user.name or '',
            'reviewers': ', '.join(self.reviewer_ids.mapped('name')),
        }

    @api.model
    def _sh_tl_is_manager(self):
        """Who sees "ყველა" and the workload tabs: project managers / admins and department heads."""
        user = self.env.user
        if user.has_group('project.group_project_manager') or user.has_group('base.group_system'):
            return True
        return bool(self.env['hr.department'].sudo().search_count([('manager_ids.user_id', '=', user.id)]))

    @api.model
    def sh_timeline_data(self, date_from, date_to, group_by='department', status='open', department_id=False,
                         user_id=False, search='', subtasks=False, mine=False):
        d_from, d_to = date.fromisoformat(date_from), date.fromisoformat(date_to)
        today = fields.Date.context_today(self)
        domain = [('is_template', '=', False), ('project_id', '!=', False)]
        uid = self.env.uid
        if mine:  # "ჩემი": my tasks and sub-tasks (assignee or main responsible)
            domain += ['|', ('user_ids', 'in', [uid]), ('sh_responsible_id', '=', uid)]
            subtasks = True
        if not subtasks:
            domain.append(('parent_id', '=', False))
        if status == 'open':
            domain.append(('state', 'not in', CLOSED))
        elif status == 'overdue':
            domain.append(('sh_is_overdue', '=', True))
        elif status == 'done':
            domain.append(('state', '=', '1_done'))
        if department_id:
            domain.append(('project_id', '=', int(department_id)))
        if user_id:
            domain.append(('user_ids', 'in', [int(user_id)]))
        if search:
            domain += ['|', ('name', 'ilike', search), ('sh_number', 'ilike', search)]
        tasks = self.search(domain, limit=MAX_TASKS, order='date_deadline asc, id asc')  # access rules apply

        items = []
        for task in tasks:
            item = task._sh_tl_item(today)
            # in the period: the bar (or its overdue tail up to today) crosses it
            last = max(item['end'], today.isoformat()) if item['overdue'] else item['end']
            if item['start'] <= date_to and last >= date_from:
                items.append((task, item))

        groups = {}
        for task, item in items:
            if group_by == 'user':
                keys = [(u.id, u.name) for u in task.user_ids] or [(0, 'დაუნიშნავი')]
            elif group_by == 'project':
                keys = [(task.sh_project_id.id or 0, task.sh_project_id.name or 'პროექტის გარეშე')]
            else:
                keys = [(task.project_id.id, task.project_id.name)]
            for key, label in keys:
                g = groups.setdefault(key, {'key': key, 'label': label, 'tasks': []})
                g['tasks'].append(item)
        result = sorted(groups.values(), key=lambda g: (g['key'] == 0, g['label'] or ''))
        for g in result:
            g['tasks'].sort(key=lambda t: (t['start'], t['end']))
            g['overdue'] = sum(1 for t in g['tasks'] if t['overdue'])

        # non-working days (weekends + public holidays) for shading
        off = []
        day = d_from
        while day <= d_to and (d_to - d_from).days <= 200:
            if not self._sh_is_working_day(day):
                off.append(day.isoformat())
            day += timedelta(days=1)

        depts = self.env['project.project'].search(
            [('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {
            'is_manager': self._sh_tl_is_manager(),
            'groups': result,
            'today': today.isoformat(),
            'off_days': off,
            'total': len(items),
            'overdue': sum(1 for _t, i in items if i['overdue']),
            'truncated': len(tasks) >= MAX_TASKS,
            'departments': [{'id': d.id, 'name': d.name} for d in depts],
            'users': [{'id': u.id, 'name': u.name} for u in users],
        }

    # ------------------------------------------------------------------ workload
    @api.model
    def sh_workload_data(self, date_from, date_to, mode='user', bucket='day', department_id=False,
                         user_id=False, subtasks=False):
        """Workload: how many open tasks each person (mode 'user') or department (mode 'team') has
        running in each day / week of the period. A task runs from its start to its deadline; an
        overdue one keeps running up to today; one without a deadline - up to today."""
        d_from, d_to = date.fromisoformat(date_from), date.fromisoformat(date_to)
        today = fields.Date.context_today(self)
        week_end = today + timedelta(days=7)
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        if not subtasks:
            base.append(('parent_id', '=', False))
        if department_id:
            base.append(('project_id', '=', int(department_id)))
        if user_id:
            base.append(('user_ids', 'in', [int(user_id)]))
        open_tasks = self.search(base + [('state', 'not in', CLOSED)], limit=MAX_TASKS)
        done_tasks = self.search(base + [('state', '=', '1_done')], limit=MAX_TASKS).filtered(
            lambda t: t.date_last_stage_update and d_from <= self._sh_tl_day(t.date_last_stage_update) <= d_to)

        # columns
        cols = []
        day = d_from
        while day <= d_to:
            last = min(day + timedelta(days=6 if bucket == 'week' else 0), d_to)
            cols.append({'key': day.isoformat(), 'start': day, 'end': last,
                         'label': day.strftime('%d.%m') if bucket == 'week' else str(day.day),
                         'off': bucket == 'day' and not self._sh_is_working_day(day),
                         'today': day <= today <= last})
            day = last + timedelta(days=1)

        spans = {}
        for t in open_tasks:
            item = t._sh_tl_item(today)
            start = date.fromisoformat(item['start'])
            end = max(date.fromisoformat(item['end']), today) if (item['overdue'] or item['open_end']) else \
                date.fromisoformat(item['end'])
            spans[t.id] = (start, end, item['overdue'])

        def row(key, label, tasks, done, people=1):
            cells = []
            for c in cols:
                ids = [t.id for t in tasks if spans[t.id][0] <= c['end'] and spans[t.id][1] >= c['start']]
                late = [i for i in ids if spans[i][2]]
                cells.append({'key': c['key'], 'count': len(ids), 'late': len(late), 'ids': ids,
                              'avg': round(len(ids) / people, 1) if people else 0})
            overdue = tasks.filtered(lambda t: spans[t.id][2])
            due = tasks.filtered(lambda t: t.date_deadline and today <= self._sh_tl_day(t.date_deadline) <= week_end)
            review = tasks.filtered(lambda t: t.stage_id.sh_kind == 'review')
            peak = max((c['count'] for c in cells), default=0)
            return {'key': key, 'label': label, 'people': people, 'cells': cells,
                    'open': len(tasks), 'open_ids': tasks.ids, 'overdue': len(overdue), 'overdue_ids': overdue.ids,
                    'due_week': len(due), 'due_ids': due.ids, 'review': len(review), 'review_ids': review.ids,
                    'done': len(done), 'done_ids': done.ids, 'peak': peak,
                    'per_person': round(len(tasks) / people, 1) if people else 0}

        rows = []
        if mode == 'team':
            for dept in (open_tasks | done_tasks).project_id.sorted('name'):
                o = open_tasks.filtered(lambda t: t.project_id == dept)
                d = done_tasks.filtered(lambda t: t.project_id == dept)
                people = len((o | d).user_ids) or 1
                rows.append(row(dept.id, dept.name, o, d, people))
        else:
            users = (open_tasks | done_tasks).user_ids
            if user_id:
                users = users.filtered(lambda u: u.id == int(user_id))
            for user in users.sorted('name'):
                o = open_tasks.filtered(lambda t: user in t.user_ids)
                d = done_tasks.filtered(lambda t: user in t.user_ids)
                rows.append(row(user.id, user.name, o, d))
            rows.sort(key=lambda r: (-r['overdue'], -r['peak'], r['label']))
            unassigned = open_tasks.filtered(lambda t: not t.user_ids)
            if unassigned:
                rows.append(row(0, 'დაუნიშნავი', unassigned, self.browse()))

        depts = self.env['project.project'].search(
            [('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        all_users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {
            'mode': mode,
            'bucket': bucket,
            'cols': [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in c.items()} for c in cols],
            'rows': rows,
            'today': today.isoformat(),
            'departments': [{'id': d.id, 'name': d.name} for d in depts],
            'users': [{'id': u.id, 'name': u.name} for u in all_users],
            'totals': {'open': len(open_tasks), 'overdue': sum(1 for s in spans.values() if s[2]),
                       'done': len(done_tasks)},
        }

    @api.model
    def sh_tasks_action(self, ids, title):
        """Click on a number / cell: those tasks in a normal list (access rules apply)."""
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'project.task',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', [int(i) for i in ids])],
            'target': 'current',
        }
