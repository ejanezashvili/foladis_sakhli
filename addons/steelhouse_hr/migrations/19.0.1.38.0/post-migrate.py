from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    """Time off periods by HR's rule (end day included, next one from the day after): an anchor that is
    the day after the current balance's end becomes that end day + "next day"; a period already running
    by the new rule keeps its balance (anchor = the day before it started)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    today = fields.Date.context_today(env['hr.employee'])
    Allocation = env['hr.leave.allocation'].with_context(active_test=False)
    for employee in env['hr.employee'].with_context(active_test=False).search([('sh_quarter_start', '!=', False)]):
        last = Allocation.search([('employee_id', '=', employee.id), ('state', '=', 'validate'),
                                  ('holiday_status_id.sh_quarter_days', '>', 0), ('date_to', '!=', False)],
                                 order='date_to desc', limit=1)
        if not last:
            continue
        anchor = employee.sh_quarter_start
        if anchor == last.date_to + timedelta(days=1):
            employee.write({'sh_quarter_start': last.date_to, 'sh_quarter_next_day': True})
        elif last.sh_quarter_start and last.date_from <= today <= last.date_to and anchor <= today:
            employee.write({'sh_quarter_start': last.date_from - timedelta(days=1), 'sh_quarter_next_day': True})
