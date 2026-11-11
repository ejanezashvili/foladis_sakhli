from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

UNITS = {'day': 'days', 'week': 'weeks', 'month': 'months', 'year': 'years'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Repeat on a date: on "შემდეგი განმეორება" a copy of the task is created in the first
    # stage ("ახალი"), whether or not the previous one is finished (daily scheduled action).
    sh_repeat = fields.Boolean('განმეორებადი', tracking=True, copy=False)
    sh_repeat_interval = fields.Integer('განმეორდეს ყოველ', default=1, copy=False)
    sh_repeat_unit = fields.Selection([
        ('day', 'დღეში'), ('week', 'კვირაში'), ('month', 'თვეში'), ('year', 'წელიწადში'),
    ], string='ერთეული', default='week', copy=False)
    sh_repeat_start = fields.Date(
        'ციკლის დაწყება', copy=False, tracking=True, default=fields.Date.context_today,
        help="საიდან დაიწყოს ათვლა (ნაგულისხმევად — დღევანდელი დღე). ცარიელი — დავალების შექმნის დღიდან.")

    @api.onchange('sh_repeat')
    def _onchange_sh_repeat_start(self):
        for task in self:
            if task.sh_repeat and not task.sh_repeat_start:
                task.sh_repeat_start = fields.Date.context_today(task)
    sh_repeat_next = fields.Date('შემდეგი განმეორება', copy=False, readonly=True,
                                 help="ითვლება ავტომატურად: ციკლის დაწყება (ან შექმნის დღე) + ინტერვალი.")
    sh_repeat_until_type = fields.Selection([
        ('forever', 'სამუდამოდ'), ('until', 'თარიღამდე'),
    ], string='ვადამდე', default='forever', copy=False)
    sh_repeat_until = fields.Date('ბოლო თარიღი', copy=False)
    sh_create_date_str = fields.Char(compute='_compute_sh_create_date_str', string='შექმნის თარიღი')
    sh_create_datetime_str = fields.Char(compute='_compute_sh_create_date_str', string='შექმნის თარიღი')
    sh_repeat_origin_id = fields.Many2one('project.task', string='განმეორების წყარო', copy=False, index=True)

    def _compute_sh_create_date_str(self):
        for task in self:
            dt = task.create_date and fields.Datetime.context_timestamp(task, task.create_date)
            task.sh_create_date_str = dt.strftime('%d.%m.%Y') if dt else ''
            task.sh_create_datetime_str = dt.strftime('%d.%m.%Y, %H:%M') if dt else ''

    @api.constrains('sh_repeat', 'sh_repeat_interval', 'sh_repeat_next', 'sh_repeat_until_type', 'sh_repeat_until')
    def _check_sh_repeat(self):
        for task in self.filtered('sh_repeat'):
            if task.sh_repeat_interval < 1:
                raise ValidationError(_("„გამეორდეს ყოველ“ უნდა იყოს 1 ან მეტი."))

    _SH_REPEAT_FIELDS = ('sh_repeat', 'sh_repeat_start', 'sh_repeat_interval', 'sh_repeat_unit')

    def _sh_plan_next(self):
        """Next occurrence = start of the cycle (or the creation day) + one step,
        moved forward to today or later."""
        today = fields.Date.context_today(self)
        for task in self:
            if not task.sh_repeat:
                task.sh_repeat_next = False
                continue
            base = task.sh_repeat_start or (task.create_date and task.create_date.date()) or today
            nxt = base + task._sh_repeat_step()
            while nxt < today:
                nxt += task._sh_repeat_step()
            task.sh_repeat_next = nxt

    @api.onchange('sh_repeat_until_type')
    def _onchange_sh_repeat_until_type(self):
        """„თარიღამდე“: by default the cycle stops after the next occurrence."""
        for task in self:
            if task.sh_repeat_until_type == 'until' and not task.sh_repeat_until:
                task.sh_repeat_until = task.sh_repeat_next or (
                    (task.sh_repeat_start or fields.Date.context_today(task)) + task._sh_repeat_step())

    def _sh_fill_until(self):
        for task in self.filtered(lambda t: t.sh_repeat and t.sh_repeat_until_type == 'until' and not t.sh_repeat_until):
            task.sh_repeat_until = task.sh_repeat_next

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks.filtered('sh_repeat')._sh_plan_next()
        tasks._sh_fill_until()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in self._SH_REPEAT_FIELDS) and 'sh_repeat_next' not in vals:
            self._sh_plan_next()
        if 'sh_repeat_until_type' in vals or 'sh_repeat' in vals:
            self._sh_fill_until()
        return res

    def _sh_repeat_step(self):
        return relativedelta(**{UNITS[self.sh_repeat_unit or 'week']: self.sh_repeat_interval or 1})

    def _sh_repeat_once(self, on_date):
        """Copy this task for the occurrence of on_date, in the department's first stage."""
        self.ensure_one()
        start = self.sh_work_start or (self.create_date and self.create_date.date())
        vals = {
            'name': self.name,
            'sh_repeat': False,
            'sh_repeat_origin_id': self.id,
            'sh_work_start': on_date,
            'state': '01_in_progress',
            'reviewer_ids': [(6, 0, self.reviewer_ids.ids)],
            'user_ids': [(6, 0, self.user_ids.ids)],
        }
        first = self.project_id.type_ids.filtered(lambda s: s.sh_kind == 'new')[:1] or self.project_id.type_ids[:1]
        if first:
            vals['stage_id'] = first.id
        if self.date_deadline and start:
            vals['date_deadline'] = self.date_deadline + timedelta(days=(on_date - start).days)
        new = self.with_context(sh_flow_internal=True).copy(vals)
        new.message_post(body=Markup(_("ავტომატურად შეიქმნა განმეორებით (%s).")) % self._get_html_link(),
                         message_type='notification', subtype_xmlid='mail.mt_note')
        return new

    @api.model
    def _cron_sh_repeat(self):
        today = fields.Date.context_today(self)
        tasks = self.search([('sh_repeat', '=', True), ('sh_repeat_next', '<=', today),
                             ('is_template', '=', False), ('project_id', '!=', False)])
        for task in tasks:
            if task.sh_repeat_until_type == 'until' and task.sh_repeat_until and task.sh_repeat_next > task.sh_repeat_until:
                task.sh_repeat = False
                continue
            # one copy per run, even if days were missed (no pile of catch-up copies)
            task._sh_repeat_once(today)
            nxt = task.sh_repeat_next + task._sh_repeat_step()
            while nxt <= today:
                nxt += task._sh_repeat_step()
            if task.sh_repeat_until_type == 'until' and task.sh_repeat_until and nxt > task.sh_repeat_until:
                task.sh_repeat = False  # last occurrence done: the cycle stops
            else:
                task.sh_repeat_next = nxt
            self.env.cr.commit()
