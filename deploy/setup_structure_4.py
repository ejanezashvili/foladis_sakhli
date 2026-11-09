"""Company answers to სტრუქტურა.docx (2026-11-09).

- ბუღალტერია: head სოფიკო ერაძე; მოლარეები report to ნინო გოგიძე (branch head) —
  the cashier position moves to "ლოჯისტიკა / ფილიალის ხელმძღვანელი".
- ნინო გოგიძე is also a chief accountant (head of "მთავარი ბუღალტრები", with the others).
- ლოჯისტიკა: head სალომე მამაგულიშვილი (also logistics chief accountant, already set).
- საცალო გაყიდვები და სერვისი: head ნინო გოგიძე.
- საქფაქტორი: head დავითი სალთხუციშვილი; card "გიორგი" (chart only) archived.
- იურიდიული / ასისტენტი (ს. აბულაძე): vacant — card archived.
- HR manager vacant; HR work temporarily by მარიამ მელელაშვილი: Time Off officer +
  responsible for HR approvals of time off types.
Then direct managers are recomputed.
Usage: python deploy/setup_structure_4.py <admin password>   (safe to re-run)
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE'}
ROOT = 'ფოლადის სახლი / '
DEPTS = {d['complete_name']: d['id'] for d in ex('hr.department', 'search_read', [[]], {'fields': ['complete_name'], 'context': C})}
dep = lambda p: DEPTS[ROOT + p]

SOFIKO, SALOME, NINO_G, DAVIT, MARIAM_M = 30, 31, 79, 23, 27
GIORGI, ABULADZE = 123, 121

ex('hr.department', 'write', [[dep('ფინანსების დეპარტამენტი / ბუღალტერია')],
                              {'manager_ids': [(6, 0, [SOFIKO])], 'sh_head_title': False}])
ex('hr.department', 'write', [[dep('ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები')],
                              {'manager_ids': [(4, NINO_G)]}])
ex('hr.department', 'write', [[dep('ლოჯისტიკა')], {'manager_ids': [(6, 0, [SALOME])]}])
retail = dep('ლოჯისტიკა / ფილიალის ხელმძღვანელი / საცალო გაყიდვები და სერვისი')
ex('hr.department', 'write', [[retail], {'manager_ids': [(6, 0, [NINO_G])]}])
ex('hr.department', 'write', [[dep('საქფაქტორი')], {'manager_ids': [(6, 0, [DAVIT])]}])

# cashiers: position and people move under the branch head
branch = dep('ლოჯისტიკა / ფილიალის ხელმძღვანელი')
cashier = ex('hr.job', 'search', [[['name', '=', 'მოლარე']]], {'context': C})
ex('hr.job', 'write', [cashier, {'department_id': branch}])
for e in ex('hr.employee', 'search_read', [[['job_id', 'in', cashier]]], {'fields': ['job_title']}):
    ex('hr.employee', 'write', [[e['id']], {'department_id': branch, 'job_title': e['job_title']}])

ex('hr.employee', 'write', [[GIORGI, ABULADZE], {'active': False}])

# HR work for Mariam Melelashvili (temporary) is a rights change: done separately, after confirmation

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
