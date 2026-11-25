"""The director refuses an HR request - the reason is required (it goes to the task's chat and to HR)."""
from odoo import fields, models


class SteelhouseHrRefuseWizard(models.TransientModel):
    _name = 'steelhouse.hr.refuse.wizard'
    _description = 'კადრების მოთხოვნის უარყოფა'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade')
    reason = fields.Text('მიზეზი', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.task_id._sh_hr_refuse(self.reason)
        return {'type': 'ir.actions.act_window_close'}
