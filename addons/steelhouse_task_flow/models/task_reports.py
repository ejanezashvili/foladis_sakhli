"""Reports of the "რეპორტინგი" app (static/src/task_reports):
- deadline compliance: tasks finished in the period - handed over on time or late, by department /
  project / employee, with a monthly trend. "Handed over" = the last move to "შემოწმებაზე" (the
  reviewer's own time does not make the assignee late); no review step -> the moment it was closed.
- holds and cancellations: how often, for how long and why tasks are put on hold or cancelled.
Hold / resume / cancel moments are kept in sh.task.flow.event (see task_returns.write)."""
import re
from datetime import date, timedelta

from odoo import api, fields, models

from .task_returns import _local, _utc
from .task_worktime import _fmt_secs

CLOSED = ('1_done', '1_canceled')
STOP_EVENTS = ('hold', 'resume', 'cancel')
MONTHS_SHORT = ['იან', 'თებ', 'მარ', 'აპრ', 'მაი', 'ივნ', 'ივლ', 'აგვ', 'სექ', 'ოქტ', 'ნოე', 'დეკ']
MAX_ITEMS = 60
NO_REASON = '(მიზეზი მითითებული არ არის)'


def _month_add(day, months):
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _norm(reason):
    """Same reason written a little differently (case, spaces, punctuation) counts as one."""
    return re.sub(r'[\s.,!?:;"„“”\'()\-–—]+', ' ', (reason or '').lower()).strip()


def _level(pct):
    if pct is None:
        return ''
    return 'good' if pct >= 85 else 'mid' if pct >= 60 else 'bad'


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # ------------------------------------------------------------------ shared
    def _sh_rep_scope(self, mine, department_id, user_id):
        """Employees see their own tasks; "ყველა" is for heads / admins (access rules still apply)."""
        manager = self._sh_tl_is_manager()
        mine = bool(mine) or not manager
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        if mine:
            base.append(('user_ids', 'in', [self.env.uid]))
        else:
            if department_id:
                dept = self.env['project.project'].browse(int(department_id))
                base.append(('project_id', 'in', dept._sh_dept_tree_ids() or [dept.id]))
            if user_id:
                base.append(('user_ids', 'in', [int(user_id)]))
        return manager, base

    def _sh_rep_lists(self):
        depts = self.env['project.project'].search(
            [('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {'departments': [{'id': d.id, 'name': d.name} for d in depts],
                'users': [{'id': u.id, 'name': u.name} for u in users]}

    def _sh_rep_keys(self, group_by):
        self.ensure_one()
        if group_by == 'department':
            return [(self.project_id.id, self.project_id.name, '')]
        if group_by == 'user':
            return [(u.id, u.name, '') for u in self.user_ids] or [(0, 'დაუნიშნავი', '')]
        project = self.sh_project_id
        return [(project.id or 0, project.name or 'პროექტის გარეშე', self.project_id.name if project else '')]

    def _sh_rep_label(self):
        return ('%s %s' % (self.sh_number or '', self.name)).strip()

    # ------------------------------------------------------------------ deadline compliance
    def _sh_deadline_split(self):
        """Finished tasks -> [{'task', 'closed', 'state': ontime / late / nodl, 'late': seconds}]."""
        last_review = {}
        events = self.env['sh.task.flow.event'].sudo().search(
            [('task_id', 'in', self.ids), ('kind', '=', 'review')], order='date')
        for event in events:
            last_review[event.task_id.id] = event.date
        out = []
        for task in self:
            closed = task.date_last_stage_update or task.write_date
            handed = min(last_review.get(task.id) or closed, closed)
            late = (handed - task.date_deadline).total_seconds() if task.date_deadline else 0
            state = 'nodl' if not task.date_deadline else 'late' if late > 0 else 'ontime'
            out.append({'task': task, 'closed': closed, 'state': state, 'late': max(late, 0)})
        return out

    @api.model
    def sh_deadline_data(self, date_from, date_to, mine=False, group_by='department', department_id=False,
                         user_id=False):
        manager, base = self._sh_rep_scope(mine, department_id, user_id)
        d_from, d_to = date.fromisoformat(date_from), date.fromisoformat(date_to)
        start, stop = _utc(d_from), _utc(d_to + timedelta(days=1))
        now = fields.Datetime.now()
        # trend: the 6 months up to the end of the period (the whole period when it is longer)
        last_month = d_to.replace(day=1)
        first_month = max(min(_month_add(last_month, -5), d_from.replace(day=1)), _month_add(last_month, -23))
        done = self.search(base + [('state', '=', '1_done'), ('date_last_stage_update', '>=', _utc(first_month)),
                                   ('date_last_stage_update', '<', stop)])
        infos = done._sh_deadline_split()
        period = [i for i in infos if start <= i['closed'] < stop]
        overdue = self.search(base + [('sh_is_overdue', '=', True)])

        def ids(items):
            return [i['task'].id for i in items]

        def stats(key, label, items, over, sub=''):
            on = [i for i in items if i['state'] == 'ontime']
            late = [i for i in items if i['state'] == 'late']
            nodl = [i for i in items if i['state'] == 'nodl']
            n = len(on) + len(late)
            pct = round(100 * len(on) / n) if n else None
            secs = [i['late'] for i in late]
            return {'key': key, 'label': label, 'sub': sub, 'done': len(items), 'done_ids': ids(items),
                    'ontime': len(on), 'ontime_ids': ids(on), 'late': len(late), 'late_ids': ids(late),
                    'nodl': len(nodl), 'nodl_ids': ids(nodl), 'pct': pct, 'level': _level(pct),
                    'avg_late': _fmt_secs(sum(secs) / len(secs)) if secs else '-',
                    'max_late': _fmt_secs(max(secs)) if secs else '-',
                    'overdue': len(over), 'overdue_ids': over.ids}

        groups = {}
        for info in period:
            for key, label, sub in info['task']._sh_rep_keys(group_by):
                groups.setdefault(key, {'label': label, 'sub': sub, 'items': [], 'over': self.browse()})['items'].append(info)
        for task in overdue:
            for key, label, sub in task._sh_rep_keys(group_by):
                g = groups.setdefault(key, {'label': label, 'sub': sub, 'items': [], 'over': self.browse()})
                g['over'] |= task
        rows = []
        for key, g in groups.items():
            row = stats(key, g['label'], g['items'], g['over'], g['sub'])
            late = sorted((i for i in g['items'] if i['state'] == 'late'), key=lambda i: -i['late'])
            items = [{'id': i['task'].id, 'label': i['task']._sh_rep_label(), 'kind': 'late',
                      'amount': _fmt_secs(i['late']), 'who': ', '.join(i['task'].user_ids.mapped('name')),
                      'date': _local(i['closed']).strftime('%d.%m.%Y')} for i in late]
            items += [{'id': t.id, 'label': t._sh_rep_label(), 'kind': 'overdue',
                       'amount': _fmt_secs((now - t.date_deadline).total_seconds()),
                       'who': ', '.join(t.user_ids.mapped('name')),
                       'date': _local(t.date_deadline).strftime('%d.%m.%Y')}
                      for t in g['over'].sorted('date_deadline')]
            row['items'] = items[:MAX_ITEMS]
            row['more'] = max(len(items) - MAX_ITEMS, 0)
            rows.append(row)
        rows.sort(key=lambda r: (r['key'] == 0, -(r['late'] + r['overdue']), r['pct'] if r['pct'] is not None else 101,
                                 r['label'] or ''))

        trend = []
        month = first_month
        while month <= last_month:
            items = [i for i in infos if (_local(i['closed']).year, _local(i['closed']).month) == (month.year, month.month)]
            on = [i for i in items if i['state'] == 'ontime']
            late = [i for i in items if i['state'] == 'late']
            n = len(on) + len(late)
            trend.append({'key': month.isoformat(), 'label': '%s %02d' % (MONTHS_SHORT[month.month - 1], month.year % 100),
                          'ontime': len(on), 'late': len(late), 'pct': round(100 * len(on) / n) if n else None,
                          'ontime_ids': ids(on), 'late_ids': ids(late),
                          'current': d_from.replace(day=1) <= month <= last_month})
            month = _month_add(month, 1)

        return dict(self._sh_rep_lists(), is_manager=manager, total=stats('all', 'სულ', period, overdue),
                    rows=rows, trend=trend)

    # ------------------------------------------------------------------ holds and cancellations
    def _sh_hold_spans(self, now):
        """Every hold of these tasks: [{'task', 'start', 'end', 'running', 'reason', 'secs'}] and the
        cancellations: [{'task', 'date', 'reason'}]."""
        events = self.env['sh.task.flow.event'].sudo().search(
            [('task_id', 'in', self.ids), ('kind', 'in', STOP_EVENTS)], order='date, id')
        spans, cancels, opened = [], [], {}
        for event in events:
            task = event.task_id
            if event.kind == 'hold':
                if task.id not in opened:
                    opened[task.id] = {'task': task, 'start': event.date, 'end': False, 'running': False,
                                       'reason': (event.reason or '').strip()}
                    spans.append(opened[task.id])
            elif event.kind == 'resume':
                span = opened.pop(task.id, None)
                if span:
                    span['end'] = event.date
            else:
                cancels.append({'task': task, 'date': event.date, 'reason': (event.reason or '').strip()})
        for span in opened.values():
            task = span['task']
            if task.stage_id.sh_kind == 'on_hold' and task.state not in CLOSED:
                span['running'] = True
            else:  # the resume moment was not recorded
                span['end'] = max(task.date_last_stage_update or span['start'], span['start'])
        running = {s['task'].id for s in spans if s['running']}
        for task in self.filtered(lambda t: t.stage_id.sh_kind == 'on_hold' and t.state not in CLOSED):
            if task.id not in running:  # on hold, but the moment was not recorded
                spans.append({'task': task, 'start': task.date_last_stage_update or task.create_date, 'end': False,
                              'running': True, 'reason': (task.hold_reason or '').strip()})
        for span in spans:
            span['secs'] = max(((span['end'] or now) - span['start']).total_seconds(), 0)
        return spans, cancels

    @api.model
    def sh_stops_data(self, date_from, date_to, mine=False, group_by='department', department_id=False,
                      user_id=False):
        manager, base = self._sh_rep_scope(mine, department_id, user_id)
        start = _utc(date.fromisoformat(date_from))
        stop = _utc(date.fromisoformat(date_to) + timedelta(days=1))
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        visible = self.search(base)  # access rules apply
        spans, cancels = visible._sh_hold_spans(now)
        held = [s for s in spans if start <= s['start'] < stop]            # put on hold in the period
        running = [s for s in spans if s['running']]                       # on hold right now
        cancelled = [c for c in cancels if start <= c['date'] < stop]

        def stale(span):
            return bool(span['running'] and span['task'].resume_date and span['task'].resume_date < today)

        def uniq(items):
            return list(dict.fromkeys(i['task'].id for i in items))

        def stats(key, label, h, r, c, sub=''):
            secs = [s['secs'] for s in h]
            late = [s for s in r if stale(s)]
            return {'key': key, 'label': label, 'sub': sub, 'holds': len(h), 'hold_ids': uniq(h),
                    'hold_tasks': len(uniq(h)), 'avg_secs': sum(secs) / len(secs) if secs else 0,
                    'avg': _fmt_secs(sum(secs) / len(secs)) if secs else '-',
                    'max': _fmt_secs(max(secs)) if secs else '-',
                    'now': len(r), 'now_ids': uniq(r), 'stale': len(late), 'stale_ids': uniq(late),
                    'cancels': len(uniq(c)), 'cancel_ids': uniq(c)}

        groups = {}

        def put(item, slot):
            for key, label, sub in item['task']._sh_rep_keys(group_by):
                g = groups.setdefault(key, {'label': label, 'sub': sub, 'h': [], 'r': [], 'c': []})
                g[slot].append(item)

        for span in held:
            put(span, 'h')
        for span in running:
            put(span, 'r')
        for cancel in cancelled:
            put(cancel, 'c')

        def hold_item(span):
            task = span['task']
            return {'id': task.id, 'label': task._sh_rep_label(), 'kind': 'now' if span['running'] else 'hold',
                    'reason': span['reason'] or NO_REASON, 'amount': _fmt_secs(span['secs']),
                    'date': _local(span['start']).strftime('%d.%m.%Y'), 'stale': stale(span),
                    'resume': task.resume_date.strftime('%d.%m.%Y') if span['running'] and task.resume_date else ''}

        rows = []
        for key, g in groups.items():
            row = stats(key, g['label'], g['h'], g['r'], g['c'], g['sub'])
            seen, items = set(), []
            for span in sorted(g['r'] + g['h'], key=lambda s: (not s['running'], -s['secs'])):
                if id(span) not in seen:
                    seen.add(id(span))
                    items.append(hold_item(span))
            items += [{'id': c['task'].id, 'label': c['task']._sh_rep_label(), 'kind': 'cancel',
                       'reason': c['reason'] or NO_REASON, 'amount': '', 'stale': False, 'resume': '',
                       'date': _local(c['date']).strftime('%d.%m.%Y')}
                      for c in sorted(g['c'], key=lambda c: c['date'], reverse=True)]
            row['items'] = items[:MAX_ITEMS]
            row['more'] = max(len(items) - MAX_ITEMS, 0)
            rows.append(row)
        top = max([r['avg_secs'] for r in rows] + [1])
        for row in rows:
            row['bar'] = round(100 * row['avg_secs'] / top)
        rows.sort(key=lambda r: (r['key'] == 0, -r['holds'], -r['now'], -r['cancels'], r['label'] or ''))

        def reasons(items, with_time):
            found = {}
            for item in items:
                text = item['reason'] or NO_REASON
                r = found.setdefault(_norm(text) or text, {'reason': text, 'count': 0, 'secs': 0.0, 'ids': []})
                r['count'] += 1
                r['secs'] += item.get('secs', 0)
                if item['task'].id not in r['ids']:
                    r['ids'].append(item['task'].id)
            out = sorted(found.values(), key=lambda r: (-r['count'], -r['secs'], r['reason']))[:12]
            for r in out:
                r['avg'] = _fmt_secs(r['secs'] / r['count']) if with_time else ''
            return out

        return dict(self._sh_rep_lists(), is_manager=manager, total=stats('all', 'სულ', held, running, cancelled),
                    rows=rows, hold_reasons=reasons(held, True), cancel_reasons=reasons(cancelled, False))

    # ------------------------------------------------------------------ history of holds / cancellations
    @api.model
    def _sh_stops_backfill(self):
        """Rebuild the hold / resume / cancel events from the stage history."""
        Event = self.env['sh.task.flow.event'].sudo()
        Event.search([('kind', 'in', STOP_EVENTS)]).unlink()
        Track = self.env['mail.tracking.value'].sudo()
        Fields = self.env['ir.model.fields']
        f_stage = Fields._get('project.task', 'stage_id')
        f_hold, f_cancel = Fields._get('project.task', 'hold_reason'), Fields._get('project.task', 'cancel_reason')
        Stage = self.env['project.task.type'].sudo()

        def reason(msg, field):
            value = msg.tracking_value_ids.filtered(lambda v: v.field_id == field)[:1]
            return value and (value.new_value_text or value.new_value_char) or False

        rows = Track.search([('field_id', '=', f_stage.id), ('mail_message_id.model', '=', 'project.task')],
                            order='create_date, id')
        holding, last_hold, last_cancel, made = set(), {}, {}, 0
        for row in rows:
            msg = row.mail_message_id
            old = Stage.browse(row.old_value_integer).exists().sh_kind
            new = Stage.browse(row.new_value_integer).exists().sh_kind
            task = self.sudo().browse(msg.res_id).exists()
            if not task or task.is_template:
                continue
            vals = {'task_id': task.id, 'date': row.create_date, 'user_id': msg.author_id.user_ids[:1].id}
            if new == 'on_hold' and old != 'on_hold':
                last_hold[task.id] = Event.create(dict(vals, kind='hold', reason=reason(msg, f_hold)))
                holding.add(task.id)
                made += 1
            elif old == 'on_hold' and new != 'on_hold':
                Event.create(dict(vals, kind='resume'))
                holding.discard(task.id)
                made += 1
            if new == 'cancelled' and old != 'cancelled':
                last_cancel[task.id] = Event.create(dict(vals, kind='cancel', reason=reason(msg, f_cancel)))
                made += 1
        # the reason of the latest hold / cancellation is also on the task itself
        for event in last_hold.values():
            if not event.reason and event.task_id.hold_reason:
                event.reason = event.task_id.hold_reason
        for event in last_cancel.values():
            if not event.reason and event.task_id.cancel_reason:
                event.reason = event.task_id.cancel_reason
        # tasks that are on hold / cancelled now, but whose move is missing from the history
        for task in self.sudo().search([('is_template', '=', False), ('stage_id.sh_kind', 'in', ['on_hold', 'cancelled'])]):
            vals = {'task_id': task.id, 'date': task.date_last_stage_update or task.write_date}
            if task.stage_id.sh_kind == 'on_hold' and task.id not in holding:
                Event.create(dict(vals, kind='hold', reason=task.hold_reason))
                made += 1
            elif task.stage_id.sh_kind == 'cancelled' and task.id not in last_cancel:
                Event.create(dict(vals, kind='cancel', reason=task.cancel_reason))
                made += 1
        return made

    @api.model
    def _sh_stops_backfill_once(self):
        """Run from the module data: fills the history the first time the report is installed."""
        params = self.env['ir.config_parameter'].sudo()
        if not params.get_param('steelhouse_task_flow.stops_backfilled'):
            self._sh_stops_backfill()
            params.set_param('steelhouse_task_flow.stops_backfilled', '1')
