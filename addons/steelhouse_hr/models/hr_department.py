from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    deputy_id = fields.Many2one(
        'hr.employee', string='შემცვლელი', tracking=True, index=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="ხელმძღვანელის შემცვლელი მისი არყოფნისას.")
