"""Required fields and sub-tasks move into the settings: first filling from the client's documents and the
people set so far (time keeping, security)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['steelhouse.hr.task.config']._sh_defaults()
