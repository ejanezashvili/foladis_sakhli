"""Fields HR adds himself (steelhouse.hr.extra.field, kept as properties of the request): one
steelhouse.hr.kind per process is created."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['steelhouse.hr.task.config']._sh_defaults()
    tasks = env['project.task'].with_context(active_test=False).search([('sh_hr_kind', '!=', False)])
    env.add_to_compute(tasks._fields['sh_hr_kind_id'], tasks)
    tasks.flush_recordset(['sh_hr_kind_id'])
