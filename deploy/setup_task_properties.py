"""Add the standard task properties (responsible, start date, category, branch) to every project.
Usage: python deploy/setup_task_properties.py <admin password>
Safe to re-run: only missing properties are added."""
import sys, xmlrpc.client as x
sys.stdout.reconfigure(encoding='ascii', errors='backslashreplace')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
DEF = [
    {'name': 'sh_responsible', 'string': 'მთავარი პასუხისმგებელი', 'type': 'many2one', 'comodel': 'res.users',
     'domain': "[('share', '=', False)]", 'view_in_cards': True},
    {'name': 'sh_date_start', 'string': 'დაწყების თარიღი', 'type': 'date', 'view_in_cards': False},
    {'name': 'sh_category', 'string': 'კატეგორია', 'type': 'selection', 'view_in_cards': False, 'selection': [
        ['admin', 'ადმინისტრაციული'], ['sales', 'გაყიდვები'], ['stock', 'მარაგი და საწყობი'],
        ['finance', 'ფინანსური'], ['tech', 'ტექნიკური'], ['other', 'სხვა']]},
    {'name': 'sh_branch', 'string': 'ფილიალი', 'type': 'selection', 'view_in_cards': False, 'selection': [
        ['main', 'ძირითადი ფილიალი'], ['vaziani3', 'ვაზიანი #3'], ['vaziani1', 'ვაზიანი 1'],
        ['vaziani2', 'ვაზიანი 2'], ['batumi', 'ბათუმის ფილიალი'], ['lilo', 'ლილო']]},
]
ids = ex('project.project', 'search', [[]])
done = 0
for pid in ids:
    cur = ex('project.project', 'read', [[pid]], {'fields': ['task_properties_definition']})[0]['task_properties_definition'] or []
    have = {d['name'] for d in cur}
    new = cur + [d for d in DEF if d['name'] not in have]
    if len(new) != len(cur):
        ex('project.project', 'write', [[pid], {'task_properties_definition': new}]); done += 1
print('projects updated', done, 'of', len(ids))
print(ex('project.project', 'read', [[ids[0]]], {'fields': ['task_properties_definition']})[0]['task_properties_definition'][0])
