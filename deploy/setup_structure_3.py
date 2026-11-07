"""Logistics as in the org chart (2026-11-07):

ლოჯისტიკა (no head)
 ├─ ლოჯისტიკის კურატორი (სალომე მამაგულიშვილი)
 │    ├─ ლოჯისტიკის ოპერატორი (not in the chart; operators from the list)
 │    └─ ავტოპარკი
 └─ ფილიალის ხელმძღვანელი (ნინო გოგიძე)       <- was "ფილიალი"
      ├─ საწყობი და ინვენტარიზაცია
      └─ საცალო გაყიდვები და სერვისი

Projects follow the department paths (renamed / created). Direct managers recomputed.
Usage: python deploy/setup_structure_3.py <admin password>   (safe to re-run)
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE'}
ROOT = 'ფოლადის სახლი / '


def paths():
    return {d['id']: d['complete_name'] for d in ex('hr.department', 'search_read', [[]],
                                                       {'fields': ['complete_name'], 'context': C})}


def by_path(p):
    return {v: k for k, v in paths().items()}[ROOT + p]


# projects are named after the department path (without the company name)
old = paths()
projects = {p['name']: p['id'] for p in ex('project.project', 'search_read', [[]], {'fields': ['name'], 'context': C})}
project_of = {did: projects[name[len(ROOT):]] for did, name in old.items() if name[len(ROOT):] in projects}

log = by_path('ლოჯისტიკა')
found = ex('hr.department', 'search', [[['name', '=', 'ლოჯისტიკის კურატორი'], ['parent_id', '=', log]]])
cur = found[0] if found else ex('hr.department', 'create', [{'name': 'ლოჯისტიკის კურატორი', 'parent_id': log}])
ex('hr.department', 'write', [[cur], {'manager_ids': [(6, 0, [31])]}])          # სალომე მამაგულიშვილი
ex('hr.department', 'write', [[log], {'manager_ids': [(6, 0, [])], 'sh_head_title': False}])
ex('hr.department', 'write', [[by_path('ლოჯისტიკა / ავტოპარკი') if ROOT + 'ლოჯისტიკა / ავტოპარკი' in old.values()
                               else by_path('ლოჯისტიკა / ლოჯისტიკის კურატორი / ავტოპარკი')], {'parent_id': cur}])
branch = ex('hr.department', 'search', [[['parent_id', '=', log], ['name', 'in', ['ფილიალი', 'ფილიალის ხელმძღვანელი']]]])[0]
ex('hr.department', 'write', [[branch], {'name': 'ფილიალის ხელმძღვანელი'}])

# Salome sits in her unit. The chart has only ავტოპარკი under the curator; the logistics
# operators from the list are the chart's warehouse "ოპერატორები" (under საწყობის მენეჯერი).
ex('hr.employee', 'write', [[31], {'department_id': cur}])
whm = by_path('ლოჯისტიკა / ფილიალის ხელმძღვანელი / საწყობი და ინვენტარიზაცია / საწყობის მენეჯერი')     if ROOT + 'ლოჯისტიკა / ფილიალის ხელმძღვანელი / საწყობი და ინვენტარიზაცია / საწყობის მენეჯერი' in old.values()     else by_path('ლოჯისტიკა / ფილიალი / საწყობი და ინვენტარიზაცია / საწყობის მენეჯერი')
op = ex('hr.job', 'search', [[['name', '=', 'ოპერატორი'], ['department_id', '=', whm]]], {'context': C})[0]
for e in ex('hr.employee', 'read', [[80, 81]], {'fields': ['job_title']}):
    ex('hr.employee', 'write', [[e['id']], {'department_id': whm, 'job_id': op, 'job_title': e['job_title']}])
ex('hr.job', 'write', [ex('hr.job', 'search', [[['name', '=', 'ლოჯისტიკის ოპერატორი']]], {'context': C}), {'active': False}])

# projects: rename to the new paths, create one for the curator unit
new = paths()
for did, pid in project_of.items():
    ex('project.project', 'write', [[pid], {'name': new[did][len(ROOT):]}], {'context': C})  # name is translatable
cur_name = new[cur][len(ROOT):]
if cur not in project_of and not ex('project.project', 'search_count', [[['name', '=', cur_name]]], {'context': C}):
    F = ['privacy_visibility', 'type_ids', 'task_properties_definition', 'allow_recurring_tasks',
         'allow_task_dependencies', 'allow_milestones', 'label_tasks', 'resource_calendar_id']
    p = ex('project.project', 'read', [[project_of[log]]], {'fields': F})[0]
    vals = {k: p[k] for k in F}
    vals.update(name=cur_name, type_ids=[(6, 0, p['type_ids'])], user_id=77,  # სალომე's user
                resource_calendar_id=p['resource_calendar_id'] and p['resource_calendar_id'][0])
    print('project', ex('project.project', 'create', [vals], {'context': {'lang': 'ka_GE'}}), cur_name)

# direct managers
D = {d['id']: d for d in ex('hr.department', 'search_read', [[]], {'fields': ['manager_ids', 'manager_id', 'parent_id']})}
changed = 0
for e in ex('hr.employee', 'search_read', [[]], {'fields': ['department_id', 'parent_id']}):
    if not e['department_id']:
        continue
    d = D[e['department_id'][0]]
    while (not d['manager_ids'] or e['id'] in d['manager_ids']) and d['parent_id']:
        d = D[d['parent_id'][0]]
    mgr = d['manager_id'] and d['manager_id'][0]
    if mgr == e['id'] or e['id'] in d['manager_ids']:
        mgr = False
    if (e['parent_id'] and e['parent_id'][0]) != mgr:
        ex('hr.employee', 'write', [[e['id']], {'parent_id': mgr or False}])
        changed += 1
print('direct managers changed', changed)
