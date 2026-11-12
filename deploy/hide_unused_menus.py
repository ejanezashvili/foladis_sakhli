"""Hide menus the company does not use (Employees: skills, learning, resume, contract templates,
challenges, onboarding plans; Time Off: mandatory days). They stay visible to admins in developer mode (group "Technical Features").

Undo: python deploy/hide_unused_menus.py <admin password> --show
Re-run after an upgrade of hr / hr_skills / hr_gamification if the menus come back.
Usage: python deploy/hide_unused_menus.py <admin password>
"""
import ast
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
SHOW = '--show' in sys.argv

MENUS = [
    'hr_skills.hr_skill_learning_menu',                  # სწავლება (certifications, trainings)
    'hr_skills.hr_employee_skill_report_menu',           # რეპორტინგი / უნარები
    'hr_skills.hr_skill_type_menu',                      # კონფიგურაცია / უნარის ტიპები
    'hr_skills.menu_human_resources_configuration_resume',  # კონფიგურაცია / რეზიუმე
    'hr.menu_hr_employee_contract_templates',            # კონფიგურაცია / კონტრაქტის შაბლონები
    'hr_gamification.menu_hr_gamification',              # კონფიგურაცია / გამოწვევები
    'hr.menu_config_plan_plan',                          # კონფიგურაცია / ადაპტაცია / გათავისუფლება
    'hr_holidays.hr_holidays_mandatory_day_menu_configuration',  # შვებულება / კონფიგურაცია / სავალდებულო სამუშაო დღეები
]


def ref(xmlid):
    mod, name = xmlid.split('.')
    r = ex('ir.model.data', 'search_read', [[['module', '=', mod], ['name', '=', name]]], {'fields': ['res_id']})
    return r and r[0]['res_id']


tech = ref('base.group_no_one')
KEY = 'steelhouse.hidden_menus'  # original groups, kept for --show
saved = ex('ir.config_parameter', 'get_param', [KEY]) or '{}'
saved = ast.literal_eval(saved) if saved else {}
for xmlid in MENUS:
    mid = ref(xmlid)
    if not mid:
        print('not found', xmlid)
        continue
    if SHOW:
        if xmlid in saved:  # menus hidden before us (already technical) stay as they were
            ex('ir.ui.menu', 'write', [[mid], {'group_ids': [(6, 0, saved.pop(xmlid))]}])
        print('shown', xmlid)
    else:
        groups = ex('ir.ui.menu', 'read', [[mid], ['group_ids']])[0]['group_ids']
        if groups != [tech]:
            saved[xmlid] = groups
        # a menu shows if the user is in ANY of its groups, so the groups are replaced
        ex('ir.ui.menu', 'write', [[mid], {'group_ids': [(6, 0, [tech])]}])
        print('hidden', xmlid)
ex('ir.config_parameter', 'set_param', [KEY, repr(saved)])
