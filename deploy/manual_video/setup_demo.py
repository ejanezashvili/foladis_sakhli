"""The demo department the video manuals are recorded on (Odoo shell on the server, idempotent):
the department "სადემონსტრაციო განყოფილება" with its board, a head and two employees - test users
only, so no real task or person is touched. cleanup_demo.py removes all of it after the recording.

The password placeholder below is replaced in a temporary copy at upload time - never commit a real one.

    sudo -u odoo odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < setup_demo.py
"""
PW = '__SH_VM_PW__'
DEPT = 'სადემონსტრაციო განყოფილება'
PEOPLE = [  # login, name, job, head?
    ('demo.manager', 'გიორგი ნიმუშაძე', 'განყოფილების ხელმძღვანელი', True),
    ('demo.employee', 'ნინო ნიმუშაძე', 'სპეციალისტი', False),
    ('demo.employee2', 'ლუკა ნიმუშაძე', 'სპეციალისტი', False),
]
assert PW and not PW.startswith('__'), 'password not set'

Users = env['res.users'].sudo().with_context(active_test=False, no_reset_password=True, mail_create_nosubscribe=True,
                                             mail_create_nolog=True, tracking_disable=True)
Employee = env['hr.employee'].sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True)
Department = env['hr.department'].sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True)
Project = env['project.project'].sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True)
groups = env.ref('base.group_user') | env.ref('project.group_project_user') | env.ref('mail.group_mail_notification_type_inbox')

root = env['hr.department'].sudo().search([('parent_id', '=', False), ('name', '=', 'ფოლადის სახლი')], limit=1)
dept = Department.search([('name', '=', DEPT)], limit=1)
if not dept:
    dept = Department.create({'name': DEPT, 'parent_id': root.id})
dept.active = True

head = Employee.browse()
out = []
for login, name, job, is_head in PEOPLE:
    user = Users.search([('login', '=', login)], limit=1)
    vals = {'name': name, 'login': login, 'password': PW, 'lang': 'ka_GE', 'tz': 'Asia/Tbilisi',
            'notification_type': 'inbox', 'active': True, 'group_ids': [(6, 0, groups.ids)]}
    if user:
        user.write(vals)
    else:
        user = Users.create(vals)
    emp = Employee.search([('user_id', '=', user.id)], limit=1)
    evals = {'name': name, 'user_id': user.id, 'department_id': dept.id, 'job_title': job, 'active': True}
    if emp:
        emp.write(evals)
    else:
        emp = Employee.create(evals)
    if is_head:
        head = emp
    out.append((login, user.id, emp.id))
dept.write({'manager_id': head.id, 'manager_ids': [(6, 0, head.ids)]} if 'manager_ids' in dept._fields else {'manager_id': head.id})
Employee.search([('department_id', '=', dept.id), ('id', '!=', head.id)]).write({'parent_id': head.id})
head.parent_id = False

project = Project.search([('sh_department_id', '=', dept.id)], limit=1)
if not project:
    src = env['project.project'].sudo().search([('sh_department_id', '!=', False), ('sh_is_department', '=', True)], order='id', limit=1)
    project = Project.create({
        'name': DEPT, 'sh_is_department': True, 'sh_department_id': dept.id,
        'privacy_visibility': src.privacy_visibility, 'type_ids': [(6, 0, src.type_ids.ids)],
        'allow_task_dependencies': src.allow_task_dependencies, 'allow_recurring_tasks': src.allow_recurring_tasks,
        'allow_milestones': src.allow_milestones, 'label_tasks': src.label_tasks,
        'resource_calendar_id': src.resource_calendar_id.id,
    })
project.active = True
env.cr.commit()
env.registry.clear_cache()
print('Q demo department', dept.id, dept.complete_name, '| project', project.id, project.name, '| code', project.sh_code,
      '| stages', [(s.id, s.sh_kind) for s in project.type_ids])
for line in out:
    print('Q user', *line)
print('Q head', head.name, '| all managers of the department:', dept.sh_all_manager_user_ids.mapped('name'))
