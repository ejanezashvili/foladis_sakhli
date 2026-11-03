from odoo import fields, models, _
from odoo.exceptions import UserError


class TaskReasonWizard(models.TransientModel):
    _name = 'steelhouse.task.reason.wizard'
    _description = 'დავალების დაბრუნება / შეჩერება / გაუქმება'

    task_ids = fields.Many2many('project.task', string='დავალებები', required=True)
    mode = fields.Selection([
        ('return', 'დაბრუნება შესასწორებლად'),
        ('hold', 'შეჩერება'),
        ('cancel', 'გაუქმება'),
    ], required=True, readonly=True)
    reason = fields.Text('მიზეზი', required=True)
    resume_date = fields.Date('განახლების სავარაუდო თარიღი')

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or '').strip():
            raise UserError(_("მიუთითეთ მიზეზი."))
        tasks = self.task_ids
        if self.mode == 'return':
            tasks._sh_check_approver(_("დაბრუნება"))
            for task in tasks:
                task._sh_move('returned', {
                    'last_return_reason': self.reason,
                    'return_count': task.return_count + 1,
                })
                task._sh_close_todo(task.reviewer_id, _("დაბრუნდა"))
                task._sh_todo(task.responsible_id or task.user_ids[:1], _("შესასწორებელია: %s", task.name), self.reason)
                task._sh_notify(task.user_ids | task.responsible_id,
                                task._sh_reason_html(_("დავალება დაბრუნდა შესასწორებლად"), self.reason))
        elif self.mode == 'hold':
            tasks._sh_check_assignee(_("შეჩერება"))
            for task in tasks:
                task._sh_move('on_hold', {'hold_reason': self.reason, 'resume_date': self.resume_date})
                extra = _("განახლების თარიღი: %s", self.resume_date) if self.resume_date else ''
                task._sh_notify(task.reviewer_id, task._sh_reason_html(_("დავალება შეჩერდა"), self.reason, extra))
        elif self.mode == 'cancel':
            tasks._sh_check_approver(_("გაუქმება"))
            for task in tasks:
                task._sh_move('cancelled', {'cancel_reason': self.reason})
                task._sh_notify(task.user_ids | task.responsible_id,
                                task._sh_reason_html(_("დავალება გაუქმდა"), self.reason))
        return {'type': 'ir.actions.act_window_close'}
