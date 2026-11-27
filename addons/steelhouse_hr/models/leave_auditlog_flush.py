"""Time off / allocation requests can be saved while the audit log (OCA auditlog) watches them.

On create, the audit log reads the new record with a throw-away cache. Creating a request also makes
its approval activity in the same call, and that activity still has values waiting to be written; the
audit log's read then fails ("Could not find all values of mail.activity(...) to flush them") and the
request is not saved. Writing everything to the database before returning fixes it - the audit log
patches `create` around the whole chain, so this runs before its snapshot.
"""
from odoo import api, models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.flush_all()
        return records


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.flush_all()
        return records
