from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SteelhouseLeaveDelegation(models.Model):
    _name = 'steelhouse.leave.delegation'
    _description = 'შემცვლელი შვებულების დროს'
    _order = 'leave_id, id'

    leave_id = fields.Many2one('hr.leave', string='შვებულება', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='leave_id.employee_id', string='თანამშრომელი', store=True)
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი', required=True)
    deputy_id = fields.Many2one('hr.employee', string='შემცვლელი')

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
        """Prefill deputies: a department head gets one line per managed department
        (with that department's deputy); others get one line for their own department."""
        for leave in self:
            if leave.delegation_ids or not leave.employee_id:
                continue
            employee = leave.employee_id
            managed = self.env['hr.department'].search([('manager_id', '=', employee.id)])
            if managed:
                lines = [{'department_id': d.id, 'deputy_id': d.deputy_id.id if d.deputy_id != employee else False}
                         for d in managed]
            elif employee.department_id:
                lines = [{'department_id': employee.department_id.id}]
            else:
                lines = []
            leave.delegation_ids = [(0, 0, vals) for vals in lines]

    def _drop_empty_delegations(self):
        self.delegation_ids.filtered(lambda l: not l.deputy_id).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._drop_empty_delegations()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        if 'delegation_ids' in vals:
            self._drop_empty_delegations()
        return res
