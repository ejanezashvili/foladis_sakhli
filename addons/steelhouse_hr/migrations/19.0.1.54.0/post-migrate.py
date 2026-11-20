from odoo import SUPERUSER_ID, api

# the company's time off types -> report categories (others stay empty: shown only when used)
BY_XMLID = {
    'hr_holidays.leave_type_paid_time_off': 'paid',
    'hr_holidays.leave_type_unpaid': 'unpaid',
    'hr_holidays.leave_type_sick_time_off': 'sick',
    'hr_holidays.l10n_ch_swissdec_illness_lt': 'sick',
    'hr_holidays.l10n_ch_swissdec_accident_lt': 'sick',
    'hr_holidays.l10n_ch_swissdec_maternity_lt': 'maternity',
    'hr_holidays.leave_type_compensatory_days': 'compensatory',
}
BY_NAME = {
    'ორსულობის, მშობიარობის და ბავშვის მოვლის შვებულება': 'maternity',
    'მივლინება': 'trip',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, kind in BY_XMLID.items():
        leave_type = env.ref(xmlid, raise_if_not_found=False)
        if leave_type and not leave_type.sh_report_kind:
            leave_type.sh_report_kind = kind
    for name, kind in BY_NAME.items():
        for leave_type in env['hr.leave.type'].with_context(lang='ka_GE').search([('name', '=', name)]):
            if not leave_type.sh_report_kind:
                leave_type.sh_report_kind = kind
