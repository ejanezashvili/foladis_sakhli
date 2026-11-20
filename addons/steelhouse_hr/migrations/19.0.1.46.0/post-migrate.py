from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """HR's report columns (once; Odoo's own time off types are protected from data updates):
    paid time off -> "paid", unpaid -> "unpaid". More types can be marked on the type form."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, kind in (('hr_holidays.leave_type_paid_time_off', 'paid'), ('hr_holidays.leave_type_unpaid', 'unpaid')):
        leave_type = env.ref(xmlid, raise_if_not_found=False)
        if leave_type and not leave_type.sh_report_kind:
            leave_type.sh_report_kind = kind
