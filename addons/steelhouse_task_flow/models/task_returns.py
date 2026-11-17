"""7.8 returned tasks: every time the reviewer sends a task back from "შემოწმებაზე"
(to "დაბრუნებული" or "მიმდინარე") is one return. Moves to review are logged too, for the share."""
from datetime import date, datetime, time, timedelta

import pytz

from odoo import api, fields, models

TZ = pytz.timezone('Asia/Tbilisi')
BACK_KINDS = ('returned', 'in_progress')


class ShTaskFlowEvent(models.Model):
    _name = 'sh.task.flow.event'
    _description = 'დავალების შემოწმება / დაბრუნება'
    _order = 'date desc, id desc'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade', index=True)
    # hold / resume / cancel feed the "შეჩერება და გაუქმება" report (task_reports.py)
    kind = fields.Selection([('review', 'შემოწმებაზე'), ('return', 'დაბრუნება'), ('hold', 'შეჩერება'),
                             ('resume', 'გაგრძელება'), ('cancel', 'გაუქმება')], required=True, index=True)
    date = fields.Datetime(required=True, index=True)
    user_id = fields.Many2one('res.users', string='ვინ')
    reason = fields.Text()


def _utc(day):
    return TZ.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)


def _local(dt):
    return pytz.utc.localize(dt).astimezone(TZ) if dt else None


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_return_count = fields.Integer('დაბრუნებები', compute='_compute_sh_returns')
    sh_return_note = fields.Char(compute='_compute_sh_returns')

    def _compute_sh_returns(self):
        Event = self.env['sh.task.flow.event'].sudo()
        for task in self:
            ret = Event.search([('task_id', '=', task.id or 0), ('kind', '=', 'return')]) if task.id else Event
            task.sh_return_count = len(ret)
            last = ret[:1]
            task.sh_return_note = last and 'ბოლო: %s%s' % (
                _local(last.date).strftime('%d.%m.%Y'), (' - „%s“' % last.reason.strip()) if last.reason else '') or False

    def write(self, vals):
        before = {t.id: t.stage_id.sh_kind for t in self} if vals.get('stage_id') else None
        res = super().write(vals)
        if before is not None:
            Event = self.env['sh.task.flow.event'].sudo()
            now = fields.Datetime.now()
            for task in self:
                old, new = before.get(task.id), task.stage_id.sh_kind
                if new == 'review' and old != 'review':
                    Event.create({'task_id': task.id, 'kind': 'review', 'date': now, 'user_id': self.env.uid})
                elif old == 'review' and new in BACK_KINDS:
                    Event.create({'task_id': task.id, 'kind': 'return', 'date': now, 'user_id': self.env.uid,
                                  'reason': vals.get('return_reason') or (task.return_reason if new == 'returned' else False)})
                if new == 'on_hold' and old != 'on_hold':
                    Event.create({'task_id': task.id, 'kind': 'hold', 'date': now, 'user_id': self.env.uid,
                                  'reason': vals.get('hold_reason') or task.hold_reason})
                elif old == 'on_hold' and new != 'on_hold':
                    Event.create({'task_id': task.id, 'kind': 'resume', 'date': now, 'user_id': self.env.uid})
                if new == 'cancelled' and old != 'cancelled':
                    Event.create({'task_id': task.id, 'kind': 'cancel', 'date': now, 'user_id': self.env.uid,
                                  'reason': vals.get('cancel_reason') or task.cancel_reason})
        return res

    @api.model
    def _sh_returns_backfill(self):
        """One-off: rebuild review / return events from the stage history."""
        Event = self.env['sh.task.flow.event'].sudo()
        Event.search([('kind', 'in', ('review', 'return'))]).unlink()
        Track = self.env['mail.tracking.value'].sudo()
        Fields = self.env['ir.model.fields']
        f_stage, f_reason = Fields._get('project.task', 'stage_id'), Fields._get('project.task', 'return_reason')
        Stage = self.env['project.task.type'].sudo()
        rows = Track.search([('field_id', '=', f_stage.id), ('mail_message_id.model', '=', 'project.task')],
                            order='create_date, id')
        made = 0
        for row in rows:
            msg = row.mail_message_id
            old = Stage.browse(row.old_value_integer).exists().sh_kind
            new = Stage.browse(row.new_value_integer).exists().sh_kind
            task = self.sudo().browse(msg.res_id).exists()
            if not task:
                continue
            vals = {'task_id': task.id, 'date': row.create_date, 'user_id': msg.author_id.user_ids[:1].id}
            if new == 'review' and old != 'review':
                Event.create(dict(vals, kind='review'))
                made += 1
            elif old == 'review' and new in BACK_KINDS:
                reason = msg.tracking_value_ids.filtered(lambda v: v.field_id == f_reason)[:1].new_value_char
                Event.create(dict(vals, kind='return', reason=reason or False))
                made += 1
        return made

    # ------------------------------------------------------------------ 7.8 report
    @api.model
    def sh_returns_data(self, date_from, date_to, mine=False, group_by='project', department_id=False, user_id=False):
        manager = self._sh_tl_is_manager()
        mine = mine or not manager
        start, stop = _utc(date.fromisoformat(date_from)), _utc(date.fromisoformat(date_to) + timedelta(days=1))
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        if mine:
            base.append(('user_ids', 'in', [self.env.uid]))
        else:
            if department_id:
                base.append(('project_id', 'in', self.env['project.project'].browse(int(department_id))._sh_dept_tree_ids() or [int(department_id)]))
            if user_id:
                base.append(('user_ids', 'in', [int(user_id)]))
        visible = self.search(base)  # access rules apply
        events = self.env['sh.task.flow.event'].sudo().search(
            [('task_id', 'in', visible.ids), ('date', '>=', start), ('date', '<', stop)])
        reviews, returns = events.filtered(lambda e: e.kind == 'review'), events.filtered(lambda e: e.kind == 'return')
        returned_tasks = returns.task_id
        rework = returned_tasks.filtered(lambda t: t.stage_id.sh_kind in BACK_KINDS)

        def stats(key, label, tasks, sub=''):
            rv = reviews.filtered(lambda e: e.task_id in tasks).task_id
            rt = returns.filtered(lambda e: e.task_id in tasks)
            rtt = rt.task_id
            now = rework & tasks
            n = len(rv | rtt)
            return {'key': key, 'label': label, 'sub': sub, 'reviewed': n, 'reviewed_ids': (rv | rtt).ids,
                    'returned': len(rtt), 'returned_ids': rtt.ids, 'returns': len(rt),
                    'pct': round(100 * len(rtt) / n) if n else 0, 'rework': len(now), 'rework_ids': now.ids}

        involved = (reviews | returns).task_id
        groups = {}
        for task in involved:
            if group_by == 'department':
                keys = [(task.project_id.id, task.project_id.name, '')]
            elif group_by == 'user':
                keys = [(u.id, u.name, '') for u in task.user_ids] or [(0, 'დაუნიშნავი', '')]
            else:
                p = task.sh_project_id
                keys = [(p.id or 0, p.name or 'პროექტის გარეშე', task.project_id.name if p else '')]
            for key, label, sub in keys:
                g = groups.setdefault(key, {'label': label, 'sub': sub, 'tasks': self.browse()})
                g['tasks'] |= task
        rows = []
        for key, g in groups.items():
            row = stats(key, g['label'], g['tasks'], g['sub'])
            row['items'] = [{
                'id': t.id, 'label': '%s %s' % (t.sh_number or '', t.name),
                'returns': len(returns.filtered(lambda e: e.task_id == t)),
                'state': 'rework' if t in rework else ('review' if t.stage_id.sh_kind == 'review' else 'other'),
                'stage': t.stage_id.name,
            } for t in g['tasks'].sorted(lambda t: -len(returns.filtered(lambda e: e.task_id == t))) if t in returned_tasks]
            rows.append(row)
        total = stats('all', 'სულ', involved)
        for r in rows:
            r['high'] = bool(r['returned'] and total['pct'] and r['pct'] >= max(total['pct'] * 1.5, total['pct'] + 10))
        rows.sort(key=lambda r: (r['key'] == 0, -r['returns'], -r['pct'], r['label']))
        recent = [{
            'task_id': e.task_id.id, 'number': e.task_id.sh_number or '', 'name': e.task_id.name,
            'reason': e.reason or '', 'who': e.user_id.name or '', 'date': _local(e.date).strftime('%d.%m'),
            'times': len(returns.filtered(lambda x: x.task_id == e.task_id)),
        } for e in returns[:8]]
        depts = self.env['project.project'].search([('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {'is_manager': manager, 'total': total, 'rows': rows, 'recent': recent,
                'all_return_ids': returned_tasks.ids,
                'departments': [{'id': d.id, 'name': d.name} for d in depts],
                'users': [{'id': u.id, 'name': u.name} for u in users]}
