"""Reload Georgian translations (overwrite) and re-apply DB-only translation fixes."""
import sys, xmlrpc.client as x
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)  # argv[1] = admin password
lid = ex('res.lang', 'search', [[['code', '=', 'ka_GE']]])[0]
w = ex('base.language.install', 'create', [{'lang_ids': [(6, 0, [lid])], 'overwrite': True}])
ex('base.language.install', 'lang_install', [[w]])
def xid(mod, name):
    return ex('ir.model.data', 'search_read', [[['module', '=', mod], ['name', '=', name]]], {'fields': ['res_id']})[0]['res_id']
FIXES = [
    ('hr', 'hr_department_view_kanban', {'Employees': 'თანამშრომელი'}),
    ('hr_holidays', 'hr_leave_view_form', {'A supporting document is required for this type of time off.':
                                           'ამ ტიპის შვებულებისთვის საჭიროა დამადასტურებელი დოკუმენტი.'}),
]
for mod, name, terms in FIXES:
    ex('ir.ui.view', 'update_field_translations', [[xid(mod, name)], 'arch_db', {'ka_GE': terms}])
# menu names that differ from the shared .po text ("Employees" is also the app name)
MENU_FIXES = [
    ('hr', 'menu_hr_employee_payroll', 'თანამშრომლების სია'),
    ('hr_holidays', 'menu_hr_holidays_my_leaves', 'ჩემი შვებულება'),
    ('hr_holidays', 'hr_leave_menu_new_request', 'კალენდარი'),
    ('hr_holidays', 'hr_leave_menu_my', 'ჩემი მოთხოვნები'),
    ('hr_holidays', 'menu_open_allocation', 'შვებულების ბალანსი'),
]
for mod, name, label in MENU_FIXES:
    ex('ir.ui.menu', 'update_field_translations', [[xid(mod, name)], 'name', {'ka_GE': label}])
priv = ex('res.groups.privilege', 'search', [[['placeholder', '=', 'No']]])
if priv:
    ex('res.groups.privilege', 'write', [priv, {'placeholder': 'არა'}])
print('reloaded; view fixes', len(FIXES), '; menu fixes', len(MENU_FIXES), '; privileges fixed', len(priv))
