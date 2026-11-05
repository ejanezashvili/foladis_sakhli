from odoo import fields, models, _
from odoo.exceptions import UserError


class TaskFlowWizard(models.TransientModel):
    _name = 'steelhouse.task.flow.wizard'
    _description = 'დავალების შეჩერება / დაბრუნება / გაუქმება'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade')
    mode = fields.Selection([
        ('on_hold', 'შეჩერება'),
        ('returned', 'დაბრუნება შესასწორებლად'),
        ('cancelled', 'გაუქმება'),
    ], required=True)
    reason = fields.Text('მიზეზი', required=True)
    resume_date = fields.Date('განახლების თარიღი')

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or '').strip():
            raise UserError(_("მიუთითეთ მიზეზი."))
        if self.mode == 'on_hold' and not self.resume_date:
            raise UserError(_("მიუთითეთ განახლების თარიღი."))
        self.task_id._sh_apply_reason(self.mode, self.reason.strip(), self.resume_date)
        return {'type': 'ir.actions.act_window_close'}
