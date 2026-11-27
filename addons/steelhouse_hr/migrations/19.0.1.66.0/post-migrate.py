"""Keep the first approvers on the existing time off requests (rule `rule_hr_leave_approver`)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['hr.leave'].with_context(active_test=False).search([])._sh_store_approvers()
