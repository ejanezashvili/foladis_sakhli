"""Company answers on the structure (2026-11-09, `Docs/სტრუქტურა — პასუხები 2026-11-09.md`):

- საქფაქტორი: head = დავითი სალთხუციშვილი (was "გიორგი"); ცინარი ღვედაშვილი reports to him
- ბუღალტერია: head = სოფიკო ერაძე ("სოფო")
- ნინო გოგიძე: added to "მთავარი ბუღალტრები" (main accountant)
- მოლარეები (ლია სალთხუციშვილი, მარინა ქევანაშვილი): report to ნინო გოგიძე (department unchanged)
- ჯანო ხოფერია, ალიკო ივანიშვილი: no user (already archived)

Open questions (გიორგი, ირმა / HR, cashiers' department, cards without users) — not changed here.
Usage: python deploy/setup_structure_4.py <admin password or API key>   (safe to re-run)
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE'}
ROOT = 'ფოლადის სახლი / '


def dept(path):
    return ex('hr.department', 'search', [[['complete_name', '=', ROOT + path]]], {'context': C})[0]


def emp(name):
    return ex('hr.employee', 'search', [[['name', '=', name]]], {'context': C})[0]


davit, sofo, nino = emp('დავითი სალთხუციშვილი'), emp('სოფიკო ერაძე'), emp('ნინო გოგიძე')

ex('hr.department', 'write', [[dept('საქფაქტორი')], {'manager_ids': [(6, 0, [davit])]}])
ex('hr.employee', 'write', [[emp('ცინარი ღვედაშვილი')], {'parent_id': davit}])

# parent_id of the cashiers is set after the head, so Odoo's own manager sync does not override it
ex('hr.department', 'write', [[dept('ფინანსების დეპარტამენტი / ბუღალტერია')], {'manager_ids': [(6, 0, [sofo])]}])
ex('hr.department', 'write', [[dept('ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები')],
                              {'manager_ids': [(4, nino)]}])
ex('hr.employee', 'write', [[emp('ლია სალთხუციშვილი'), emp('მარინა ქევანაშვილი')], {'parent_id': nino}])

users = ex('res.users', 'search', [[['name', 'in', ['ჯანო ხოფერია', 'ალიკო ივანიშვილი']]]])
if users:
    ex('res.users', 'write', [users, {'active': False}])
print('done')
