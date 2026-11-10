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
    sh_repeat_interval = fields.Integer('გამეორდეს ყოველ', default=1, copy=False)
    sh_repeat_unit = fields.Selection([
        ('day', 'დღეში'), ('week', 'კვირაში'), ('month', 'თვეში'), ('year', 'წელიწადში'),
    ], string='ერთეული', default='week', copy=False)
    sh_repeat_next = fields.Date('შემდეგი განმეორება', tracking=True, copy=False)
    sh_repeat_until_type = fields.Selection([
        ('forever', 'სამუდამოდ'), ('until', 'თარიღამდე'),
    ], string='ვადამდე', default='forever', copy=False)
    sh_repeat_until = fields.Date('ბოლო თარიღი', copy=False)
    sh_repeat_origin_id = fields.Many2one('project.task', string='განმეორების წყარო', copy=False, index=True)

    @api.constrains('sh_repeat', 'sh_repeat_interval', 'sh_repeat_next', 'sh_repeat_until_type', 'sh_repeat_until')
    def _check_sh_repeat(self):
        for task in self.filtered('sh_repeat'):
            if task.sh_repeat_interval < 1:
                raise ValidationError(_("„გამეორდეს ყოველ“ უნდა იყოს 1 ან მეტი."))
            if not task.sh_repeat_next:
                raise ValidationError(_("მიუთითეთ „შემდეგი განმეორების“ თარიღი."))
            if task.sh_repeat_until_type == 'until' and not task.sh_repeat_until:
                raise ValidationError(_("მიუთითეთ ბოლო თარიღი."))

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
            while task.sh_repeat and task.sh_repeat_next and task.sh_repeat_next <= today:
                if task.sh_repeat_until_type == 'until' and task.sh_repeat_until and task.sh_repeat_next > task.sh_repeat_until:
                    task.sh_repeat = False
                    break
                task._sh_repeat_once(task.sh_repeat_next)
                task.sh_repeat_next = task.sh_repeat_next + task._sh_repeat_step()
            self.env.cr.commit()
