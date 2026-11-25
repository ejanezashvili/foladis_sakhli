"""Removes everything setup_demo.py and the recordings made (Odoo shell on the server): the demo tasks
and templates, their chats, the demo department with its board, the three demo employees and users.
A user that cannot be deleted (something still points at it) is archived instead, with a login that
can no longer be used. Dry run: DRY = True.

    sudo -u odoo odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < cleanup_demo.py
"""
DRY = False
DEPT = 'სადემონსტრაციო განყოფილება'
LOGINS = ['demo.manager', 'demo.employee', 'demo.employee2']

ctx = dict(active_test=False, tracking_disable=True, mail_create_nolog=True, sh_flow_internal=True)
Users = env['res.users'].sudo().with_context(**ctx)
users = Users.search([('login', 'in', LOGINS)])
dept = env['hr.department'].sudo().with_context(**ctx).search([('name', '=', DEPT)])
projects = env['project.project'].sudo().with_context(**ctx).search([('sh_department_id', 'in', dept.ids)])
tasks = env['project.task'].sudo().with_context(**ctx).search(
    ['|', ('project_id', 'in', projects.ids), ('create_uid', 'in', users.ids)])
employees = env['hr.employee'].sudo().with_context(**ctx).search([('user_id', 'in', users.ids)])
partners = users.partner_id
channels = env['discuss.channel'].sudo().with_context(**ctx).search([('create_uid', 'in', users.ids)])
print('Q found: users', users.mapped('login'), '| department', dept.mapped('complete_name'), '| projects', projects.mapped('name'),
      '| tasks', len(tasks), '| employees', employees.mapped('name'), '| chats', len(channels))
# nothing real may be in the list: every task must belong to the demo board or be a demo user's own
foreign = tasks.filtered(lambda t: t.project_id and t.project_id not in projects)
print('Q tasks outside the demo board (made by the demo users, removed too):', foreign.mapped('name'))

if not DRY:
    for model, domain in (('mail.activity', [('res_model', '=', 'project.task'), ('res_id', 'in', tasks.ids)]),
                          ('mail.activity', [('user_id', 'in', users.ids)]),
                          ('mail.notification', [('res_partner_id', 'in', partners.ids)])):
        env[model].sudo().search(domain).unlink()
    if 'sh.task.flow.event' in env:
        env['sh.task.flow.event'].sudo().search([('task_id', 'in', tasks.ids)]).unlink()
    env['ir.attachment'].sudo().search([('res_model', '=', 'project.task'), ('res_id', 'in', tasks.ids)]).unlink()
    tasks.unlink()
    channels.unlink()
    env['mail.message'].sudo().search([('author_id', 'in', partners.ids)]).unlink()
    projects.unlink()
    employees.unlink()
    dept.unlink()
    env.cr.commit()
    for user in users:
        login, partner = user.login, user.partner_id
        try:
            with env.cr.savepoint():
                user.unlink()
                partner.unlink()
            print('Q deleted', login)
        except Exception as e:
            user.write({'active': False, 'login': 'removed.%s.%d' % (login, user.id), 'password': False})
            print('Q archived (could not be deleted):', login, '|', str(e).splitlines()[0][:160])
    env.cr.commit()
    env.registry.clear_cache()
    print('Q left: users', Users.search_count([('login', 'in', LOGINS)]), '| department',
          env['hr.department'].sudo().with_context(active_test=False).search_count([('name', '=', DEPT)]),
          '| tasks', env['project.task'].sudo().with_context(active_test=False).search_count([('id', 'in', tasks.ids)]))
else:
    env.cr.rollback()
    print('Q dry run - nothing removed')
