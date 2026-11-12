from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Manual progress no longer counts: recompute the progress of tasks that had one."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env['project.task'].with_context(active_test=False).search([('sh_manual_progress', '!=', 0)])
    if tasks:
        env.add_to_compute(env['project.task']._fields['sh_progress'], tasks)
        tasks.flush_recordset(['sh_progress'])
