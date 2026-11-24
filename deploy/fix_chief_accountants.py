"""2026-11-24 (user): a chart box with people under it is not a head of its own. "მთავარი ბუღალტრები" (a box
under ბუღალტერია) had its 6 chief accountants as heads, so an assistant's time off needed all six. The head
of the unit approves: ბუღალტერია - სოფიკო ერაძე, then ზეზვა. The box stays (for the chart), without heads.

Run in the Odoo shell on the server:
    sudo -u odoo odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < fix_chief_accountants.py
"""
DEPT = 'ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები'

D = env['hr.department'].sudo()
dept = D.search([]).filtered(lambda d: (d.complete_name or '').endswith(DEPT))
assert len(dept) == 1, dept
people = env['hr.employee'].sudo().search([('department_id', 'child_of', dept.ids)])


def show(tag):
    for e in people.sorted('name'):
        leave = env['hr.leave'].new({'employee_id': e.id, 'holiday_status_id': 1})
        print('FIX', tag, e.name, '| head', e.parent_id.name, '| card approver', e.leave_manager_id.name,
              '| approves:', leave._sh_approval_text())


show('before')
old_head_users = dept.manager_ids.user_id
dept.write({'manager_ids': [(5, 0, 0)], 'sh_head_title': False})
people.invalidate_recordset()
# the card's time off approver ("დამმტკიცებლები" - "შვებულება") followed the old heads: now the new head
for e in people.filtered(lambda e: e.leave_manager_id in old_head_users and e.parent_id.user_id):
    e.leave_manager_id = e.parent_id.user_id
show('after')
env.cr.commit()
print('FIX done, heads now', dept.manager_ids.mapped('name'))
