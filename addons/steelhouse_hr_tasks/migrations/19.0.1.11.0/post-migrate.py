"""The required fields of a process are kept in steelhouse.hr.field (HR may not read ir.model.fields):
the list is filled and the client's defaults set again."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['steelhouse.hr.task.config']._sh_defaults()
