"""Contacts: filter and group by job position ("თანამდებობა"), 2026-11-09.

Creates (all through the API, no module install needed):
- model x_sh_job_title — one record per distinct employee job title (hr.employee.job_title),
  with x_count = number of contacts holding it (shown in the "Search More" dialog)
- res.partner.x_sh_job_title_id — the contact's job position (from its employee)
- automation: employee created / job title or contact changed -> title record + contact field
- views: Contacts search — field "თანამდებობა" (typing shows positions + "Search More…" with
  all positions, multi-select) and group by "თანამდებობა"; Contacts list — column "თანამდებობა"
- fills the field for all existing employees

Usage: python deploy/setup_contacts_job_filter.py <admin password or API key>   (safe to re-run)
Undo: delete the views, the automation, the field x_sh_job_title_id and the model x_sh_job_title.
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
LABEL = 'თანამდებობა'
MODEL = 'x_sh_job_title'


def one(model, domain):
    ids = ex(model, 'search', [domain], {'context': {'active_test': False}})
    return ids[0] if ids else False


def upsert(model, domain, vals):
    rid = one(model, domain)
    if rid:
        ex(model, 'write', [[rid], vals])
        return rid
    return ex(model, 'create', [vals])


def xmlid(ref):
    mod, name = ref.split('.')
    return ex('ir.model.data', 'search_read', [[['module', '=', mod], ['name', '=', name]]], {'fields': ['res_id']})[0]['res_id']


# 1. model with job titles
model_id = one('ir.model', [['model', '=', MODEL]]) or ex('ir.model', 'create', [{
    'name': LABEL, 'model': MODEL, 'order': 'x_name',
    'field_id': [(0, 0, {'name': 'x_name', 'field_description': LABEL, 'ttype': 'char', 'required': True})],
}])
upsert('ir.model.fields', [['model', '=', MODEL], ['name', '=', 'x_count']], {
    'model_id': model_id, 'name': 'x_count', 'field_description': 'კონტაქტები', 'ttype': 'integer',
    'store': False, 'depends': '',
    'compute': "for r in self:\n"
               "    r['x_count'] = self.env['res.partner'].search_count([('x_sh_job_title_id', '=', r.id)])",
})
user_group = xmlid('base.group_user')
upsert('ir.model.access', [['model_id', '=', model_id], ['group_id', '=', user_group]], {
    'name': 'x_sh_job_title user', 'model_id': model_id, 'group_id': user_group,
    'perm_read': True, 'perm_write': False, 'perm_create': False, 'perm_unlink': False,
})
upsert('ir.ui.view', [['model', '=', MODEL], ['type', '=', 'list']], {
    'name': 'x_sh_job_title.list', 'model': MODEL, 'type': 'list',
    'arch_db': f'<list string="{LABEL}"><field name="x_name"/><field name="x_count"/></list>',
})

# 2. field on contacts
partner_model = one('ir.model', [['model', '=', 'res.partner']])
upsert('ir.model.fields', [['model', '=', 'res.partner'], ['name', '=', 'x_sh_job_title_id']], {
    'model_id': partner_model, 'name': 'x_sh_job_title_id', 'field_description': LABEL,
    'ttype': 'many2one', 'relation': MODEL, 'on_delete': 'set null', 'index': True,
})

# 3. automation: keep titles and contacts in sync with employees
code = (
    "for e in records:\n"
    "    title = (e.job_title or '').strip()\n"
    "    rec = env['x_sh_job_title']\n"
    "    if title:\n"
    "        rec = rec.sudo().search([('x_name', '=', title)], limit=1) or rec.sudo().create({'x_name': title})\n"
    "    if e.work_contact_id and e.work_contact_id.x_sh_job_title_id != rec:\n"
    "        e.work_contact_id.sudo().write({'x_sh_job_title_id': rec.id})\n"
)
emp_model = one('ir.model', [['model', '=', 'hr.employee']])
trig = ex('ir.model.fields', 'search', [[['model', '=', 'hr.employee'], ['name', 'in', ['job_title', 'work_contact_id']]]])
action = upsert('ir.actions.server', [['name', '=', 'კონტაქტის თანამდებობის განახლება'], ['model_id', '=', emp_model]], {
    'name': 'კონტაქტის თანამდებობის განახლება', 'model_id': emp_model, 'state': 'code', 'code': code,
})
upsert('base.automation', [['name', '=', 'კონტაქტის თანამდებობა თანამშრომლიდან']], {
    'name': 'კონტაქტის თანამდებობა თანამშრომლიდან', 'model_id': emp_model, 'trigger': 'on_create_or_write',
    'trigger_field_ids': [(6, 0, trig)], 'action_server_ids': [(6, 0, [action])], 'active': True,
})

# 4. views
upsert('ir.ui.view', [['name', '=', 'res.partner.search.sh_job_title']], {
    'name': 'res.partner.search.sh_job_title', 'model': 'res.partner', 'type': 'search', 'mode': 'extension',
    'inherit_id': xmlid('base.view_res_partner_filter'),
    'arch_db': '<data>'
               f'<field name="user_id" position="after"><field name="x_sh_job_title_id" string="{LABEL}"/></field>'
               f'<filter name="group_country" position="after"><filter name="group_sh_job_title" string="{LABEL}" '
               "context=\"{'group_by': 'x_sh_job_title_id'}\"/></filter>"
               '</data>',
})
upsert('ir.ui.view', [['name', '=', 'res.partner.list.sh_job_title']], {
    'name': 'res.partner.list.sh_job_title', 'model': 'res.partner', 'type': 'list', 'mode': 'extension',
    'inherit_id': xmlid('base.view_partner_tree'),
    'arch_db': f'<field name="email" position="before"><field name="x_sh_job_title_id" string="{LABEL}" optional="show"/></field>',
})

# 5. fill existing contacts (runs the same server action on every employee)
emps = ex('hr.employee', 'search', [[]], {'context': {'active_test': False}})
ex('ir.actions.server', 'run', [[action]], {'context': {'active_model': 'hr.employee', 'active_ids': emps}})
print('titles:', ex(MODEL, 'search_count', [[]]),
      '| contacts with title:', ex('res.partner', 'search_count', [[['x_sh_job_title_id', '!=', False]]],
                                   {'context': {'active_test': False}}))
