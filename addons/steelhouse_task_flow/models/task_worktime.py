import pytz

from odoo import api, fields, models

TZ = pytz.timezone('Asia/Tbilisi')

# "სამუშაო დრო": runs from "მიღებული" until "შემოწმებაზე" (real time).
# Returned tasks continue - the extra time is added to the earlier one.
RUN_KINDS = ('accepted', 'in_progress', 'on_hold', 'returned')
STOP_KINDS = ('review', 'done', 'cancelled')


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
                task.sh_work_time = '⏱ %s — მიმდინარეობს' % _fmt_secs(secs)
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
