from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SteelhouseLeaveDelegation(models.Model):
    _name = 'steelhouse.leave.delegation'
    _description = 'შემცვლელი შვებულების დროს'
    _order = 'leave_id, id'

    leave_id = fields.Many2one('hr.leave', string='შვებულება', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='leave_id.employee_id', string='თანამშრომელი', store=True)
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი', required=True)
    deputy_id = fields.Many2one('hr.employee', string='შემცვლელი', required=True)

    @api.constrains('deputy_id', 'employee_id')
    def _check_deputy_not_self(self):
        for line in self:
            if line.deputy_id and line.deputy_id == line.employee_id:
                raise ValidationError(_("საკუთარი თავი შემცვლელად ვერ მიუთითებთ."))

    @api.constrains('department_id', 'leave_id')
    def _check_unique_department(self):
        for line in self:
            same = line.leave_id.delegation_ids.filtered(lambda l: l.department_id == line.department_id)
            if len(same) > 1:
                raise ValidationError(_("დეპარტამენტი „%s“ ორჯერაა მითითებული.", line.department_id.name))


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    delegation_ids = fields.One2many(
        'steelhouse.leave.delegation', 'leave_id', string='შემცვლელები', copy=False,
        help="ვინ ჩაიბარებს თითოეული დეპარტამენტის საკითხებს შვებულების დროს.")

    @api.onchange('employee_id')
    def _onchange_employee_prefill_delegations(self):
        """A department head gets one line per department they manage, with that department's deputy."""
        for leave in self:
            if leave.delegation_ids or not leave.employee_id:
                continue
            managed = self.env['hr.department'].search([('manager_id', '=', leave.employee_id.id)])
            leave.delegation_ids = [
                (0, 0, {
                    'department_id': dept.id,
                    'deputy_id': dept.deputy_id.id if dept.deputy_id != leave.employee_id else False,
                })
                for dept in managed
            ]
