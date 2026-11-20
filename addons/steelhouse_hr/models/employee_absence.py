"""Employee card: "on leave from .. to .., deputy: .." while the employee's approved time off runs
(both the HR card and the card every employee sees - hr.employee.public)."""
from odoo import api, fields, models


def _absence_text(employee):
    """employee: hr.employee (sudo). Text for the card, or False."""
    leave = employee._sh_current_absence()
    if not leave:
        return False
    period = '%s - %s' % (leave.request_date_from.strftime('%d.%m.%Y'), leave.request_date_to.strftime('%d.%m.%Y'))
    lines = leave.delegation_ids.filtered('deputy_id')
    if len(lines) == 1:
        deputies = lines.deputy_id.name
    elif lines:
        deputies = ', '.join('%s (%s)' % (line.deputy_id.name, line.department_id.name) for line in lines)
    else:
        deputies = 'არ არის მითითებული'
    return 'შვებულებაშია (%s): %s · შემცვლელი: %s' % (leave.holiday_status_id.name, period, deputies)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sh_absence_info = fields.Char(string='შვებულებაშია', compute='_compute_sh_absence_info')

    @api.depends_context('uid')
    def _compute_sh_absence_info(self):
        for employee in self:
            employee.sh_absence_info = _absence_text(employee.sudo()) if employee.id else False


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sh_absence_info = fields.Char(string='შვებულებაშია', compute='_compute_sh_absence_info')

    def _compute_sh_absence_info(self):
        for employee in self:
            real = self.env['hr.employee'].sudo().browse(employee.id).exists() if employee.id else False
            employee.sh_absence_info = _absence_text(real) if real else False
