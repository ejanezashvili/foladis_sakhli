"""Create the deadline / escalation automation rules (requirements 4.2, 4.4, 4.5, 4.6).
Usage: python deploy/setup_automation_rules.py <admin password>
Safe to re-run: existing rules (same name) are skipped. Note: with a working-day calendar Odoo counts the current day, so 'before 2' = reminder on the previous working day.
Thresholds can be changed later in
Settings > Technical > Automation Rules."""
import sys, xmlrpc.client as x
sys.stdout.reconfigure(encoding='ascii', errors='backslashreplace')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
model = ex('ir.model', 'search', [[['model', '=', 'project.task']]])[0]
fld = lambda n: ex('ir.model.fields', 'search', [[['model', '=', 'project.task'], ['name', '=', n]]])[0]
OPEN = "[('is_closed', '=', False), ('is_template', '=', False), ('project_id', '!=', False)]"

CODE_REMIND = '''
for task in records:
    if not task.date_deadline or task.date_deadline <= datetime.datetime.now():
        continue
    when = task.date_deadline.date() if task.date_deadline else False
    for user in task.user_ids:
        task.activity_schedule('mail.mail_activity_data_todo', date_deadline=when, user_id=user.id,
                               summary='ვადა იწურება ხვალ: %s' % task.name)
'''
CODE_OVERDUE = '''
for task in records:
    for boss in (task.reviewer_ids or task.create_uid):
        task.activity_schedule('mail.mail_activity_data_todo', user_id=boss.id,
                               summary='ვადაგადაცილებულია: %s' % task.name,
                               note='შემსრულებლები: %s' % ', '.join(task.user_ids.mapped('name')))
'''
CODE_ESCALATE = '''
for task in records:
    bosses = task.reviewer_ids or task.create_uid
    emps = env['hr.employee'].search([('user_id', 'in', bosses.ids)]) if bosses else env['hr.employee']
    for top in emps.sh_manager_ids.user_id:  # all equal heads of the reviewers
        task.activity_schedule('mail.mail_activity_data_todo', user_id=top.id,
                               summary='ესკალაცია — 3 დღით ვადაგადაცილებული: %s' % task.name,
                               note='შემმოწმებელი: %s; შემსრულებლები: %s' % (', '.join(bosses.mapped('name')), ', '.join(task.user_ids.mapped('name'))))
'''
CODE_REVIEW = '''
for task in records:
    for boss in (task.reviewer_ids or task.create_uid):
        task.activity_schedule('mail.mail_activity_data_todo', user_id=boss.id,
                               summary='დასადასტურებელია (2 დღეა შემოწმებაზე): %s' % task.name)
'''
RULES = [
    ('4.2 შეხსენება: ვადამდე 1 დღე', fld('date_deadline'), 2, 'before', OPEN, CODE_REMIND),
    ('4.4 ვადაგადაცილება: შემმოწმებელს', fld('date_deadline'), 0, 'after', OPEN, CODE_OVERDUE),
    ('4.5 ესკალაცია: ვადიდან 3 დღე', fld('date_deadline'), 3, 'after', OPEN, CODE_ESCALATE),
    ('4.6 დასადასტურებელი: შემოწმებაზე 2 დღე', fld('date_last_stage_update'), 2, 'after',
     OPEN[:-1] + ", ('stage_id.sh_kind', '=', 'review')]", CODE_REVIEW),
]
for name, date_field, rng, mode, domain, code in RULES:
    if ex('base.automation', 'search_count', [[['name', '=', name]]]):
        print('exists', name); continue
    rid = ex('base.automation', 'create', [{
        'name': name, 'model_id': model, 'trigger': 'on_time',
        'trg_date_id': date_field, 'trg_date_range': rng, 'trg_date_range_type': 'day',
        'trg_date_range_mode': mode, 'filter_domain': domain,
        'action_server_ids': [(0, 0, {'name': name, 'model_id': model, 'state': 'code', 'code': code})],
    }])
    print('created', rid, name)
