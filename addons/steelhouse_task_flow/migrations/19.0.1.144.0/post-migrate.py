from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The main task of a sequence now counts its steps in the progress: recompute those tasks."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env['project.task'].with_context(active_test=False).search(
        [('depend_on_ids', '!=', False), ('sh_is_step', '=', False)])
    if tasks:
        env.add_to_compute(env['project.task']._fields['sh_progress'], tasks)
        tasks.flush_recordset(['sh_progress'])
