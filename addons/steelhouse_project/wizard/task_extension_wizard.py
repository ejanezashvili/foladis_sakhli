from odoo import fields, models, _
from odoo.exceptions import UserError


class TaskExtensionWizard(models.TransientModel):
    _name = 'steelhouse.task.extension.wizard'
    _description = 'ვადის გადაწევის მოთხოვნა'

    task_id = fields.Many2one('project.task', string='დავალება', required=True)
    current_deadline = fields.Datetime(related='task_id.date_deadline', string='მიმდინარე ვადა')
    new_deadline = fields.Datetime('ახალი ვადა', required=True)
    reason = fields.Text('მიზეზი', required=True)

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        if task.date_deadline and self.new_deadline <= task.date_deadline:
            raise UserError(_("ახალი ვადა უნდა იყოს მიმდინარე ვადაზე გვიან."))
        request = self.env['steelhouse.task.extension.request'].create({
            'task_id': task.id,
            'old_deadline': task.date_deadline,
            'new_deadline': self.new_deadline,
            'reason': self.reason,
        })
        request._post_request_message()
        return {'type': 'ir.actions.act_window_close'}
