"""Undo deploy/fix_chief_accountants.py (2026-11-24, the user wants to look at the old state first):
"მთავარი ბუღალტრები" gets its 6 heads back (თათია ჯაბუა first - the assistants' direct head), the title
"მთავარი ბუღალტერი", and the two assistants' card time off approver თათია ჯაბუა again.
"""
DEPT = 'ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები'
HEADS = ['თათია ჯაბუა', 'მარიამ ტორაძე', 'მარიამი კვეზერელი', 'ნათია კახაბრიშვილი', 'ნინო გოგიძე', 'სალომე მამაგულიშვილი']

E = env['hr.employee'].sudo()
dept = env['hr.department'].sudo().search([]).filtered(lambda d: (d.complete_name or '').endswith(DEPT))
assert len(dept) == 1, dept
heads = E.browse()
for name in HEADS:
    e = E.search([('name', '=', name)])
    assert len(e) == 1, name
    heads |= e
dept.write({'manager_ids': [(6, 0, heads.ids)], 'sh_head_title': 'მთავარი ბუღალტერი'})
if dept.manager_id != heads[:1]:
    dept.write({'manager_id': heads[:1].id})
people = E.search([('department_id', 'child_of', dept.ids)])
people.invalidate_recordset()
for e in people.filtered(lambda e: e not in heads):
    e.leave_manager_id = heads[:1].user_id
for e in people.sorted('name'):
    leave = env['hr.leave'].new({'employee_id': e.id, 'holiday_status_id': 1})
    print('UNDO', e.name, '| head', e.parent_id.name, '| card approver', e.leave_manager_id.name, '| approves:', leave._sh_approval_text())
env.cr.commit()
print('UNDO heads', dept.manager_ids.mapped('name'), '| main', dept.manager_id.name, '| title', dept.sh_head_title)
