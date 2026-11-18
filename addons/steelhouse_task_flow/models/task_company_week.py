""""კომპანიის კვირა": the company-wide weekly summary for project administrators, shown on top of
"მთავარი" and sent to them on the first working day of the week (with the weekly digest).
Numbers come from the same places as the reports (deadline split, flow events), so they match."""
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models

from .task_reports import _level
from .task_returns import _utc

CLOSED = ('1_done', '1_canceled')
ATTENTION = 10


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def _sh_cw_allowed(self):
        user = self.env.user
        return user.has_group('project.group_project_manager') or user.has_group('base.group_system')

    @api.model
    def _sh_cw_counts(self, Task, base, start, stop):
        """created / done / on time % / returns of one week (start, stop: UTC datetimes).
        On time % is by deadline: of the tasks due this week, how many were handed over in time."""
        created = Task.search_count(base + [('create_date', '>=', start), ('create_date', '<', stop)])
        done = Task.search(base + [('state', '=', '1_done'), ('date_last_stage_update', '>=', start),
                                   ('date_last_stage_update', '<', stop)])
        split = Task._sh_due_split(base, start, stop)
        on = sum(1 for i in split if i['state'] == 'ontime')
        late = sum(1 for i in split if i['state'] == 'late')
        pct = round(100 * on / (on + late)) if on + late else None
        returns = self.env['sh.task.flow.event'].sudo().search_count(
            [('kind', '=', 'return'), ('date', '>=', start), ('date', '<', stop),
             ('task_id.is_template', '=', False)])
        return {'created': created, 'done': len(done), 'done_ids': done.ids, 'ontime': on, 'late': late,
                'pct': pct, 'level': _level(pct), 'returns': returns, 'split': split}

    @api.model
    def sh_company_week_data(self, offset=0):
        if not self._sh_cw_allowed():
            return {'allowed': False}
        offset = int(offset or 0)
        today = fields.Date.context_today(self)
        w_start = today - timedelta(days=today.weekday()) - timedelta(days=7 * offset)
        w_end = w_start + timedelta(days=6)
        start, stop = _utc(w_start), _utc(w_end + timedelta(days=1))
        Task = self.sudo()
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        cur = self._sh_cw_counts(Task, base, start, stop)
        prev = self._sh_cw_counts(Task, base, _utc(w_start - timedelta(days=7)), start)
        open_tasks = Task.search(base + [('state', 'not in', CLOSED)])
        overdue = open_tasks.filtered('sh_is_overdue')
        on_hold = open_tasks.filtered(lambda t: t.stage_id.sh_kind == 'on_hold')
        now = fields.Datetime.now()
        day = lambda dt: fields.Datetime.context_timestamp(self, dt).date() if dt else False

        def trend(key):
            a, b = cur[key], prev[key]
            if a is None or b is None or a == b:
                return 0
            return 1 if a > b else -1

        # ---- departments
        depts = {}

        def dept_of(task):
            p = task.project_id
            return depts.setdefault(p.id, {'id': p.id, 'name': p.name, 'open_ids': [], 'overdue_ids': [],
                                           'done_ids': [], 'ontime': 0, 'late': 0, 'pending': 0})
        for task in open_tasks:
            d = dept_of(task)
            d['open_ids'].append(task.id)
            if task.sh_is_overdue:
                d['overdue_ids'].append(task.id)
        for task in Task.browse(cur['done_ids']):
            dept_of(task)['done_ids'].append(task.id)
        for info in cur['split']:
            dept_of(info['task'])[info['state']] += 1
        dept_rows = []
        for d in depts.values():
            n = d['ontime'] + d['late']
            d['pct'] = round(100 * d['ontime'] / n) if n else None
            d['level'] = _level(d['pct'])
            d.update(open=len(d['open_ids']), overdue=len(d['overdue_ids']), done=len(d['done_ids']))
            dept_rows.append(d)
        dept_rows.sort(key=lambda d: (-d['overdue'], d['pct'] if d['pct'] is not None else 101, d['name'] or ''))

        # ---- needs attention
        events = self.env['sh.task.flow.event'].sudo()
        review_since = {}
        for e in events.search([('task_id', 'in', open_tasks.ids), ('kind', '=', 'review')], order='date'):
            review_since[e.task_id.id] = e.date
        returns_of = {}
        for e in events.search([('task_id', 'in', open_tasks.ids), ('kind', '=', 'return')]):
            returns_of[e.task_id.id] = returns_of.get(e.task_id.id, 0) + 1
        items = []

        def item(task, tag, kind, note, weight):
            items.append({'id': task.id, 'name': task.name, 'number': task.sh_number or '',
                          'department': task.project_id.name or '', 'tag': tag, 'kind': kind,
                          'note': note, 'who': ', '.join(task.user_ids.mapped('name')), 'weight': weight})
        for t in overdue.filtered(lambda t: t.priority in ('2', '3')):
            days = (today - day(t.date_deadline)).days if t.date_deadline else 0
            item(t, 'კრიტიკული' if t.priority == '3' else 'მაღალი', 'late',
                 '%s დღით გადაცილებული' % max(days, 0), 300 + days + (50 if t.priority == '3' else 0))
        for t in on_hold.filtered('hold_date'):
            days = (today - t.hold_date).days
            if days >= 3:
                item(t, 'შეჩერებული', 'hold', '%s დღეა შეჩერებულია%s' % (
                    days, (' - ' + t.hold_reason) if t.hold_reason else ''), 200 + days)
        for t in open_tasks.filtered(lambda t: t.stage_id.sh_kind == 'review' and t.id in review_since):
            hours = (now - review_since[t.id]).total_seconds() / 3600
            if hours >= 48:
                item(t, 'შემოწმებაზე', 'review', '%s დღეა ელოდება შემმოწმებელს' % int(hours // 24), 100 + hours / 24)
        for t in open_tasks.filtered(lambda t: returns_of.get(t.id, 0) >= 2):
            item(t, 'დაბრუნებული', 'return', '%s-ჯერ დაბრუნდა შემოწმებიდან' % returns_of[t.id], 50 + returns_of[t.id])
        seen, attention = set(), []
        for it in sorted(items, key=lambda i: -i['weight']):
            if it['id'] not in seen:
                seen.add(it['id'])
                attention.append(it)

        # ---- deadlines of this week (always the current week)
        c_start = today - timedelta(days=today.weekday())
        c_end = c_start + timedelta(days=6)
        # main tasks only: sequence steps are shown inside their task
        due = open_tasks.filtered(lambda t: t.date_deadline and not t.sh_is_step
                                  and c_start <= day(t.date_deadline) <= c_end)
        due_by = {}
        for t in due:
            due_by.setdefault(t.project_id.name or '', []).append(t.id)
        due_rows = sorted(({'name': k, 'count': len(v), 'ids': v} for k, v in due_by.items()),
                          key=lambda r: -r['count'])

        # ---- time off: who is away this week / next week, requests waiting for approval
        Leave = self.env['hr.leave'].sudo()
        heads = self.env['hr.department'].sudo().search([]).mapped('manager_ids')

        def away(a, b):
            leaves = Leave.search([('state', '=', 'validate'), ('request_date_from', '<=', b),
                                   ('request_date_to', '>=', a)], order='request_date_from')
            return [{'name': lv.employee_id.name, 'head': lv.employee_id in heads,
                     'type': lv.holiday_status_id.name,
                     'dates': '%s - %s' % (lv.request_date_from.strftime('%d.%m'), lv.request_date_to.strftime('%d.%m'))}
                    for lv in leaves]
        pending = Leave.search_count([('state', 'in', ('confirm', 'validate1'))])

        return {
            'allowed': True,
            'offset': offset,
            'label': '%s - %s' % (w_start.strftime('%d.%m'), w_end.strftime('%d.%m.%Y')),
            'kpi': {
                'created': cur['created'], 'created_prev': prev['created'], 'created_trend': trend('created'),
                'done': cur['done'], 'done_prev': prev['done'], 'done_trend': trend('done'), 'done_ids': cur['done_ids'],
                'pct': cur['pct'], 'pct_prev': prev['pct'], 'pct_trend': trend('pct'), 'level': cur['level'],
                'ontime': cur['ontime'], 'late': cur['late'],
                'returns': cur['returns'], 'returns_prev': prev['returns'], 'returns_trend': trend('returns'),
                'overdue': len(overdue), 'overdue_ids': overdue.ids,
                'on_hold': len(on_hold), 'on_hold_ids': on_hold.ids,
            },
            'departments': dept_rows,
            'attention': attention[:ATTENTION],
            'attention_total': len(attention),
            'attention_ids': [a['id'] for a in attention],
            'due_total': len(due), 'due_ids': due.ids, 'due_rows': due_rows[:6],
            'away_now': away(c_start, c_end),
            'away_next': away(c_end + timedelta(days=1), c_end + timedelta(days=7)),
            'leave_pending': pending,
        }

    # ------------------------------------------------------------------ Monday message
    def _sh_company_week_post(self):
        """Short company summary to the project administrators (OdooBot chat, with the weekly digest)."""
        group = self.env.ref('project.group_project_manager')
        admins = group.sudo().all_user_ids if 'all_user_ids' in group._fields else group.sudo().user_ids
        admins = admins.filtered(lambda u: u.active and not u.share and u.employee_ids)
        for user in admins:
            d = self.with_user(user).with_context(tz=user.tz or 'Asia/Tbilisi').sh_company_week_data(offset=1)
            if not d.get('allowed'):
                continue
            k = d['kpi']
            pct = '%s%%' % k['pct'] if k['pct'] is not None else '-'
            body = Markup(
                '<p><b>კომპანიის კვირა: %s</b></p>'
                '<p>შემოვიდა: <b>%s</b> · დასრულდა: <b>%s</b> · ვადების დაცვა: <b>%s</b><br/>'
                'ახლა ვადაგადაცილებული: <b>%s</b> · შეჩერებული: <b>%s</b> · დაბრუნებები: <b>%s</b><br/>'
                'ყურადღება მიაქციეთ: <b>%s</b> დავალებას · ამ კვირის ვადები: <b>%s</b> · '
                'შვებულების მოთხოვნა ელოდება: <b>%s</b></p>'
                '<p><a href="/odoo/action-steelhouse_task_flow.action_sh_task_dashboard">გახსენით „მთავარი“</a></p>'
            ) % (d['label'], k['created'], k['done'], pct, k['overdue'], k['on_hold'], k['returns'],
                 d['attention_total'], d['due_total'], d['leave_pending'])
            self._sh_digest_post(user, 'კომპანიის კვირა: %s' % d['label'], body)

    def _sh_send_weekly_digest(self, today):
        res = super()._sh_send_weekly_digest(today)
        self.sudo()._sh_company_week_post()
        return res
