from datetime import datetime

import pytz

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """4.4 / 4.5 move from automation rules into the module (task_notify.py)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    rules = env['base.automation'].with_context(active_test=False).search(
        ['|', ('name', '=like', '4.4 %'), ('name', '=like', '4.5 %')])
    rules.write({'active': False})
    # already escalated by the old rule 4.5 -> do not escalate again
    tasks = env['project.task'].search([('sh_is_overdue', '=', True)])
    tasks.filtered(lambda t: t.activity_ids.filtered(lambda a: (a.summary or '').startswith('ესკალაცია'))).write(
        {'sh_escalated': True})
    # no weekly summary in the week of the install; the first one goes out next week
    today = datetime.now(pytz.timezone('Asia/Tbilisi')).date()
    env['ir.config_parameter'].set_param('steelhouse_task_flow.digest_week', '%s-W%02d' % today.isocalendar()[:2])
    # e-mail is not set up yet: everyone gets notifications in Odoo
    env['res.users'].with_context(active_test=False).search([('notification_type', '=', 'email'), ('share', '=', False)]).write(
        {'notification_type': 'inbox'})
