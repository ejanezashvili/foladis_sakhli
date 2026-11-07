"""Second pass after checking the structure against the updated employee list
(Docs/თანამშრომლების სია (1).xlsx), the org chart PDF and the user's screenshots (2026-11-07).

- Top level: ზეზვა and დავითი are equal heads (deputy removed).
- Call centre: ნათია ენუქიძე is a head together with ანა ხაბულიანი.
- მამუკა ივანაშვილი: main department ავტოპარკი, also head of ბალასტი.
- სალომე მამაგულიშვილი is also a chief accountant (head of მთავარი ბუღალტრები).
- ნანა როსტომაშვილი also holds საქფაქტორი / საოპერაციო მენეჯერი (extra position).
- People named in the chart but missing from the list get an employee card as written
  (no login): გიორგი (საქფაქტორი), ა. ძამაშვილი (საწყობი), ალექსანდრე არაბული and
  გოგიაშვილი (ნადირული), პ. ცისკარიშვილი (ბალასტი, consultant).
- Not in the list and not named in the chart: ირმა, ჯანო, ალიკო - employee cards archived.
- ცინარი ღვედაშვილი gets an "ოპერატორი" position in საქფაქტორი.
Then each employee's direct manager is recomputed.

Usage: python deploy/setup_structure_2.py <admin password>   (safe to re-run)
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE'}
ROOT = 'ფოლადის სახლი'
DEPTS = {d['complete_name']: d['id'] for d in ex('hr.department', 'search_read', [[]],
                                                    {'fields': ['complete_name'], 'context': C})}
dep = lambda path: DEPTS[ROOT + (' / ' + path if path else '')]


def job(name, did):
    found = ex('hr.job', 'search', [[['name', '=', name], ['department_id', '=', did]]], {'context': C})
    return found[0] if found else ex('hr.job', 'create', [{'name': name, 'department_id': did, 'no_of_recruitment': 0}],
                                     {'context': {'lang': 'ka_GE'}})


def card(name, did, title, job_id=False):
    found = ex('hr.employee', 'search', [[['name', '=', name]]])
    if found:
        return found[0]
    return ex('hr.employee', 'create', [{'name': name, 'department_id': did, 'job_title': title, 'job_id': job_id}])


def add_heads(did, ids):
    ex('hr.department', 'write', [[did], {'manager_ids': [(4, i) for i in ids]}])


ZEZVA, DAVIT = 22, 23
ex('hr.department', 'write', [[dep('')], {'manager_ids': [(6, 0, [ZEZVA, DAVIT])], 'deputy_id': False}])
add_heads(dep('Call ცენტრის გაყიდვები'), [45])                                    # ნათია ენუქიძე
ex('hr.employee', 'write', [[33], {'department_id': dep('ლოჯისტიკა / ავტოპარკი')}])  # მამუკა ივანაშვილი
add_heads(dep('ბალასტი'), [33])
add_heads(dep('ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები'), [31])  # სალომე მამაგულიშვილი

sqf = dep('საქფაქტორი')
ex('hr.employee', 'write', [[24], {'sh_extra_job_ids': [(4, job('საოპერაციო მენეჯერი', sqf))]}])  # ნანა
ex('hr.employee', 'write', [[25], {'job_id': job('ოპერატორი', sqf), 'job_title': 'ოპერატორი'}])  # ცინარი

giorgi = card('გიორგი', sqf, 'ხელმძღვანელი')
ex('hr.department', 'write', [[sqf], {'manager_ids': [(6, 0, [giorgi])]}])
wh = dep('ლოჯისტიკა / ფილიალი / საწყობი და ინვენტარიზაცია')
ex('hr.department', 'write', [[wh], {'manager_ids': [(6, 0, [card('ა. ძამაშვილი', wh, 'საწყობის და ინვენტარიზაციის ხელმძღვანელი')])]}])
nad = dep('ნადირულის მეურნეობა')
ex('hr.department', 'write', [[nad], {'manager_ids': [(6, 0, [card('ალექსანდრე არაბული', nad, 'მენეჯერი'),
                                                              card('გოგიაშვილი', nad, 'მენეჯერი')])]}])
bal = dep('ბალასტი')
card('პ. ცისკარიშვილი', bal, 'კონსულტანტი', job('კონსულტანტი', bal))

# bookkeeping has its own head in the chart (not named, not in the list): vacant, staff go up to Sofiko
ex('hr.department', 'write', [[dep('ფინანსების დეპარტამენტი / ბუღალტერია')],
                              {'manager_ids': [(6, 0, [])], 'sh_head_title': 'განყოფილების ხელმძღვანელი'}])

ex('hr.employee', 'write', [[26, 29, 71], {'active': False}])  # ირმა, ჯანო, ალიკო
ex('res.users', 'write', [[36], {'active': True}])             # ჰომა: in the list, login restored

# direct managers: own department heads, else the nearest heads above
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
