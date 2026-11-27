import pytz

from odoo import api, fields, models

TZ = pytz.timezone('Asia/Tbilisi')

# "სამუშაო დრო": runs from the acceptance ("ახალი" -> "მიმდინარე") until "შემოწმებაზე" (real time), paused while "შეჩერებული".
# Returned / resumed tasks continue - the extra time is added to the earlier one.
# The first acceptance also fills an empty "სამუშაოს დაწყება" (sh_work_start) with that day.
RUN_KINDS = ('accepted', 'in_progress', 'returned')
STOP_KINDS = ('review', 'done', 'cancelled', 'on_hold')


def _fmt_secs(secs):
    mins = int(secs // 60)
    days, rest = divmod(mins, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return '%d დღე %d სთ' % (days, hours)
    if hours:
        return '%d სთ %d წთ' % (hours, mins)
    return '%d წთ' % mins


def _fmt_dt(dt):
    return pytz.utc.localize(dt).astimezone(TZ).strftime('%d.%m.%Y, %H:%M') if dt else ''


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_wt_first = fields.Datetime('სამუშაოს ათვლის დასაწყისი', readonly=True, copy=False)
    sh_wt_run_from = fields.Datetime(readonly=True, copy=False)
    sh_wt_secs = fields.Float(readonly=True, copy=False)
    sh_wt_end = fields.Datetime('სამუშაოს ათვლის დასასრული', readonly=True, copy=False)
    sh_work_time = fields.Char('სამუშაო დრო', compute='_compute_sh_work_time')
    sh_work_time_note = fields.Char(compute='_compute_sh_work_time')
    sh_work_running = fields.Boolean(compute='_compute_sh_work_time')

    @api.depends('sh_wt_first', 'sh_wt_run_from', 'sh_wt_secs', 'sh_wt_end')
    def _compute_sh_work_time(self):
        now = fields.Datetime.now()
        for task in self:
            secs = task.sh_wt_secs or 0.0
            if task.sh_wt_run_from:
                secs += (now - task.sh_wt_run_from).total_seconds()
            task.sh_work_running = bool(task.sh_wt_run_from)
            if not task.sh_wt_first:
                task.sh_work_time = False
                task.sh_work_time_note = False
            elif task.sh_wt_run_from:
                task.sh_work_time = '⏱ %s - მიმდინარეობს' % _fmt_secs(secs)
                task.sh_work_time_note = 'მიღებულია: %s' % _fmt_dt(task.sh_wt_first)
            else:
                task.sh_work_time = '✔ %s' % _fmt_secs(secs)
                task.sh_work_time_note = '%s → %s' % (_fmt_dt(task.sh_wt_first), _fmt_dt(task.sh_wt_end))

    def _sh_wt_apply(self, kind, when):
        for task in self:
            vals = {}
            if kind in RUN_KINDS:
                if not task.sh_wt_run_from:
                    vals['sh_wt_run_from'] = when
                if not task.sh_wt_first:
                    vals['sh_wt_first'] = when
                    # "სამუშაოს დაწყება": the day of the first acceptance, unless a date was planned.
                    # Not on a repeating original - its work start is the base of the copies' deadlines.
                    if not task.sh_work_start and not task.sh_repeat and not task.is_template:
                        vals['sh_work_start'] = pytz.utc.localize(when).astimezone(TZ).date()
            elif kind in STOP_KINDS and task.sh_wt_run_from:
                vals.update(sh_wt_secs=(task.sh_wt_secs or 0.0) + (when - task.sh_wt_run_from).total_seconds(),
                            sh_wt_run_from=False, sh_wt_end=when)
            if vals:
                super(ProjectTask, task.sudo().with_context(sh_flow_internal=True, mail_notrack=True)).write(vals)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('stage_id') and not self.env.context.get('sh_wt_skip'):
            for task in self:
                task._sh_wt_apply(task.stage_id.sh_kind, fields.Datetime.now())
        return res

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        for task in tasks:
            if task.stage_id.sh_kind in RUN_KINDS:
                task._sh_wt_apply(task.stage_id.sh_kind, fields.Datetime.now())
        return tasks

    @api.model
    def _sh_wt_backfill(self):
        """One-off: rebuild the work time of existing tasks from the stage history."""
        Track = self.env['mail.tracking.value'].sudo()
        field = self.env['ir.model.fields']._get('project.task', 'stage_id')
        Stage = self.env['project.task.type'].sudo()
        done = 0
        for task in self.sudo().search([('is_template', '=', False)]):
            rows = Track.search([('field_id', '=', field.id), ('mail_message_id.model', '=', 'project.task'),
                                 ('mail_message_id.res_id', '=', task.id)], order='create_date, id')
            if not rows:
                continue
            super(ProjectTask, task.with_context(sh_flow_internal=True, mail_notrack=True)).write(
                {'sh_wt_first': False, 'sh_wt_run_from': False, 'sh_wt_secs': 0.0, 'sh_wt_end': False})
            for row in rows:
                stage = Stage.browse(row.new_value_integer).exists()  # the stage may have been deleted
                if stage:
                    task._sh_wt_apply(stage.sh_kind, row.create_date)
            # history can miss the last move (e.g. closed with the status button): stop at its closing time
            if task.sh_wt_run_from and task.stage_id.sh_kind in STOP_KINDS:
                closed = task.date_last_stage_update or task.write_date
                end = max(closed, task.sh_wt_run_from)
                task._sh_wt_apply(task.stage_id.sh_kind, end)
            done += 1
        return done

    # ------------------------------------------------------------------ 7.7 report
    @api.model
    def sh_worktime_data(self, date_from, date_to, mine=False, department_id=False, user_id=False):
        """Average work time: tasks that reached "შემოწმებაზე" / done in the period, by department
        and employee. The "ყველა" scope is for heads only; access rules apply."""
        from datetime import date, datetime, time, timedelta
        manager = self._sh_tl_is_manager()
        mine = mine or not manager
        start = TZ.localize(datetime.combine(date.fromisoformat(date_from), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        stop = TZ.localize(datetime.combine(date.fromisoformat(date_to) + timedelta(days=1), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        if mine:
            base.append(('user_ids', 'in', [self.env.uid]))
        else:
            if department_id:
                base.append(('project_id', 'in', self.env['project.project'].browse(int(department_id))._sh_dept_tree_ids() or [int(department_id)]))
            if user_id:
                base.append(('user_ids', 'in', [int(user_id)]))
        done = self.search(base + [('sh_wt_run_from', '=', False), ('sh_wt_end', '>=', start), ('sh_wt_end', '<', stop),
                                   ('stage_id.sh_kind', 'in', ['review', 'done'])])
        running = self.search(base + [('sh_wt_run_from', '!=', False)])

        def stats(key, label, d, r):
            secs = [t.sh_wt_secs or 0.0 for t in d]
            avg = sum(secs) / len(secs) if secs else 0
            return {'key': key, 'label': label, 'count': len(d), 'ids': d.ids, 'avg': avg,
                    'avg_str': _fmt_secs(avg) if secs else '-',
                    'min_str': _fmt_secs(min(secs)) if secs else '-',
                    'max_str': _fmt_secs(max(secs)) if secs else '-',
                    'running': len(r), 'running_ids': r.ids}

        total = stats('all', 'სულ', done, running)
        rows = []
        for dept in (done | running).project_id.sorted('name'):
            d = done.filtered(lambda t: t.project_id == dept)
            r = running.filtered(lambda t: t.project_id == dept)
            row = stats(dept.id, dept.name, d, r)
            people = (d | r).user_ids
            if mine:
                people = people.filtered(lambda u: u.id == self.env.uid)
            elif user_id:
                people = people.filtered(lambda u: u.id == int(user_id))
            row['users'] = [stats('%s_%s' % (dept.id, u.id), u.name, d.filtered(lambda t: u in t.user_ids),
                                  r.filtered(lambda t: u in t.user_ids)) for u in people.sorted('name')]
            rows.append(row)
        top = max([x['avg'] for x in rows] + [u['avg'] for x in rows for u in x['users']] + [1])
        for x in [x for x in rows] + [u for x in rows for u in x['users']]:
            x['slow'] = bool(total['avg'] and x['count'] and x['avg'] > total['avg'] * 1.5)
            x['bar'] = round(100 * x['avg'] / top)
        depts = self.env['project.project'].search([('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {'is_manager': manager, 'total': total, 'rows': rows,
                'departments': [{'id': d.id, 'name': d.name} for d in depts],
                'users': [{'id': u.id, 'name': u.name} for u in users]}
