"""Request templates (D-14): the required fields move from the settings (one list per built-in process) to the
template; the built-in templates get their order, the settings and their menu items."""
from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists


def migrate(cr, version):
    for kind in ('vacancy', 'hire', 'dismissal'):
        old = 'sh_hrt_cfg_reqf_%s_rel' % kind
        if table_exists(cr, old):
            cr.execute('INSERT INTO sh_hr_kind_required_field_rel (kind_id, field_id) '
                       'SELECT k.id, r.field_id FROM ' + old + ' r JOIN steelhouse_hr_kind k ON k.kind = %s '
                       'ON CONFLICT DO NOTHING', [kind])
    env = api.Environment(cr, SUPERUSER_ID, {})
    Kind = env['steelhouse.hr.kind'].with_context(active_test=False)
    for seq, kind in enumerate(('vacancy', 'hire', 'dismissal'), start=1):
        Kind.search([('kind', '=', kind)]).write({'sequence': seq})
    env['steelhouse.hr.task.config']._sh_defaults()
    Kind.search([])._sh_rebuild()
