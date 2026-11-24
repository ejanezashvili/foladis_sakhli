"""Who sees which tasks - the client's list (Excel "თანამშრომლების სია", column "როლები", 2026-11-24).

Fills the page Projects - Configuration - "დავალებების ხილვა" (steelhouse_task_flow, models/task_visibility.py).
Everyone not listed here sees only the jobs they take part in. Run in the Odoo shell on the server, after
the module is upgraded to 19.0.1.176.0 or later (idempotent - re-running sets the same values):

    sudo -u odoo odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < setup_task_visibility.py

Dry run (prints only, changes nothing): put DRY = True below.
People are found by the employee's name; a name that is not found is printed and skipped.
"""
DRY = False

# sees every task of every department
SEE_ALL = [
    'დავითი სალთხუციშვილი',
    'მარიამ ჩილინგარაშვილი',
    'სოფიკო ერაძე',
    'გიორგი მდივნიშვილი',
]
# sees the tasks of everyone below them in the employees' hierarchy ("თავის დაქვემდებარებულებს")
SEE_SUBORDINATES = [
    'ანა ხაბულიანი',
    'ნათია ენუქიძე',
    'ალექსანდრე ბერინაშვილი',
    'ნანა ინდუაშვილი',
    'ნინო გოგიძე',
    'ანა მეკოკიშვილი',
    'გიგი ამირაშვილი',
]
# sees every task of these departments
SEE_DEPARTMENTS = {
    'სალომე მამაგულიშვილი': ['ავტოპარკი'],
}
# sees the tasks of these people
SEE_PEOPLE = {
    'სალომე მამაგულიშვილი': ['ქრისტი პატარაია'],
    'მარიამი კვეზერელი': ['თამუნა ბართია', 'ქეთევან ქარუმიძე'],
    'ნათია კახაბრიშვილი': ['თამუნა ბართია', 'თინათინ ღვალაძე'],
    'ნინო გოგილაშვილი': ['ანა კუპრაშვილი', 'ლუკა მერაბიშვილი'],
    'ანა კუპრაშვილი': ['ნინო გოგილაშვილი', 'ლუკა მერაბიშვილი'],
    'ლილი გულბიანი': ['ფათემეჰ მუსავიანი'],
    'ჰომა ვალაეიბარჰაღ': ['ეკატერინე ვალიშვილი'],
    'ეკატერინე ვალიშვილი': ['ჰომა ვალაეიბარჰაღ'],
    'ანა არაბული': ['სალომე წურწუმია', 'მაჰბოუბეჰ თარყი'],
    'სალომე წურწუმია': ['ანა არაბული', 'მაჰბოუბეჰ თარყი'],
    'ანა გურგენიძე': ['ნატო თხელიძე', 'ვასილ ამირაშვილი', 'სალომე თათრიაშვილი', 'მარიამ დევნოსაძე'],
    'ნატო თხელიძე': ['ანა გურგენიძე', 'ვასილ ამირაშვილი', 'სალომე თათრიაშვილი', 'მარიამ დევნოსაძე'],
    'სალომე თათრიაშვილი': ['მარიამ დევნოსაძე'],
    'მარიამ დევნოსაძე': ['სალომე თათრიაშვილი'],
    'ნინო ბერიძე': ['შორენა დვალი', 'ნუგზარ ქურხული', 'ზაზა ნათელაძე'],
    'შორენა დვალი': ['ნინო ბერიძე', 'ნუგზარ ქურხული', 'ზაზა ნათელაძე'],
    'თამარ ჩხაიძე': ['თამუნა ბართია'],
}

Employee = env['hr.employee'].sudo().with_context(active_test=False)
Department = env['hr.department'].sudo()
missing = []


def user_of(name):
    name = ' '.join(name.split())
    emp = Employee.search([('name', '=ilike', name), ('user_id', '!=', False)], limit=1)
    if not emp:
        # the same words in another order or with another ending ("მარიამი" / "მარიამ")
        first, last = name.split()[0], name.split()[-1]
        found = Employee.search([('name', 'ilike', last), ('name', 'ilike', first[:4]), ('user_id', '!=', False)])
        emp = found if len(found) == 1 else emp
    if not emp:
        missing.append(name)
    return emp.user_id


plan = {}
for name in SEE_ALL:
    plan.setdefault(name, {})['sh_see_all_tasks'] = True
for name in SEE_SUBORDINATES:
    plan.setdefault(name, {})['sh_see_subordinates'] = True
for name, depts in SEE_DEPARTMENTS.items():
    found = Department.browse()
    for dept in depts:
        match = Department.search([('name', 'ilike', dept)])
        if not match:
            missing.append('დეპარტამენტი: ' + dept)
        found |= match
    plan.setdefault(name, {})['sh_see_department_ids'] = [(6, 0, found.ids)]
for name, people in SEE_PEOPLE.items():
    users = env['res.users'].sudo().browse()
    for person in people:
        users |= user_of(person)
    plan.setdefault(name, {})['sh_see_user_ids'] = [(6, 0, users.ids)]

for name, vals in plan.items():
    user = user_of(name)
    if not user:
        continue
    if not DRY:
        user.write(vals)
    line = ['VISIBILITY', name, '->', user.login]
    if vals.get('sh_see_all_tasks'):
        line.append('| all')
    if vals.get('sh_see_subordinates'):
        mine = Employee.search([('user_id', '=', user.id)])
        below = Employee.search([('id', 'child_of', mine.ids), ('id', 'not in', mine.ids)])
        line.append('| subordinates: %d (%s)' % (len(below), ', '.join(below.mapped('name')) or 'NONE - set the manager on the employee cards'))
    if vals.get('sh_see_department_ids'):
        line.append('| departments: ' + ', '.join(Department.browse(vals['sh_see_department_ids'][0][2]).mapped('complete_name')))
    if vals.get('sh_see_user_ids'):
        line.append('| people: ' + ', '.join(env['res.users'].sudo().browse(vals['sh_see_user_ids'][0][2]).mapped('name')))
    print(*line)

print('VISIBILITY not found:', sorted(set(missing)) or 'nobody')
if DRY:
    env.cr.rollback()
    print('VISIBILITY dry run - nothing saved')
else:
    env.cr.commit()
    print('VISIBILITY saved')
