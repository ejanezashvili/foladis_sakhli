"""4.1 assignment rule, working-day calendar on time rules (4.8), Georgian public holidays 2026-2027.
Usage: python deploy/setup_automation_rules_2.py <admin password>  (run after setup_automation_rules.py; safe to re-run)
Holidays: verify the list with the company each year; add next year here or in Time Off > Configuration > Public Holidays."""
import sys, datetime as dt, xmlrpc.client as x
sys.stdout.reconfigure(encoding='ascii', errors='backslashreplace')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
model = ex('ir.model', 'search', [[['model', '=', 'project.task']]])[0]
fld = lambda n: ex('ir.model.fields', 'search', [[['model', '=', 'project.task'], ['name', '=', n]]])[0]
OPEN = "[('is_closed', '=', False), ('is_template', '=', False), ('project_id', '!=', False)]"

# 4.8: count reminders/escalations in working days (company calendar, public holidays included)
cal = ex('res.company', 'read', [[1]], {'fields': ['resource_calendar_id']})[0]['resource_calendar_id'][0]
for prefix in ('4.2', '4.5', '4.6'):
    ids = ex('base.automation', 'search', [[['name', '=like', prefix + ' %']]])
    ex('base.automation', 'write', [ids, {'trg_date_calendar_id': cal}])
print('working-day calendar set on 4.2, 4.5, 4.6')

# 4.1: activity for newly assigned users (also visible without e-mail)
CODE_ASSIGN = '''
for task in records:
    stale = task.activity_ids.filtered(lambda a: a.user_id not in task.user_ids and (a.summary or '').startswith('თქვენ დაგენიშნათ'))
    stale.unlink()
    for user in task.user_ids:
        if user == env.user:
            continue
        already = task.activity_ids.filtered(lambda a: a.user_id == user and (a.summary or '').startswith('თქვენ დაგენიშნათ'))
        if already:
            continue
        task.activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                               date_deadline=task.date_deadline.date() if task.date_deadline else False,
                               summary='თქვენ დაგენიშნათ დავალება: %s' % task.name)
'''
name = '4.1 ახალი დავალება: შემსრულებელს'
if not ex('base.automation', 'search_count', [[['name', '=', name]]]):
    ex('base.automation', 'create', [{
        'name': name, 'model_id': model, 'trigger': 'on_create_or_write',
        'trigger_field_ids': [(6, 0, [fld('user_ids')])], 'filter_domain': OPEN,
        'action_server_ids': [(0, 0, {'name': name, 'model_id': model, 'state': 'code', 'code': CODE_ASSIGN})],
    }])
    print('created', name)

# 4.8: Georgian public holidays (Tbilisi time = UTC+4)
HOLIDAYS = [
    ('2026-11-23', 'გიორგობა'),
    ('2027-01-01', 'ახალი წელი'), ('2027-01-02', 'ახალი წელი'), ('2027-01-07', 'შობა'),
    ('2027-01-19', 'ნათლისღება'), ('2027-03-03', 'დედის დღე'), ('2027-03-08', 'ქალთა საერთაშორისო დღე'),
    ('2027-04-09', 'ეროვნული ერთიანობის დღე'), ('2027-04-30', 'დიდი პარასკევი'), ('2027-05-01', 'დიდი შაბათი'),
    ('2027-05-02', 'აღდგომა'), ('2027-05-03', 'აღდგომის ორშაბათი'), ('2027-05-09', 'ფაშიზმზე გამარჯვების დღე'),
    ('2027-05-12', 'წმ. ანდრია პირველწოდებულის დღე'), ('2027-05-17', 'ოჯახის სიწმინდის დღე'),
    ('2027-05-26', 'დამოუკიდებლობის დღე'), ('2027-08-28', 'მარიამობა'), ('2027-10-14', 'სვეტიცხოვლობა'),
    ('2027-11-23', 'გიორგობა'),
]
made = 0
for day, label in HOLIDAYS:
    d = dt.datetime.strptime(day, '%Y-%m-%d')
    start = (d - dt.timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
    end = (d + dt.timedelta(hours=19, minutes=59, seconds=59)).strftime('%Y-%m-%d %H:%M:%S')
    if ex('resource.calendar.leaves', 'search_count', [[['resource_id', '=', False], ['date_from', '=', start]]]):
        continue
    ex('resource.calendar.leaves', 'create', [{'name': label, 'date_from': start, 'date_to': end,
                                               'company_id': 1, 'calendar_id': False, 'time_type': 'leave'}])
    made += 1
print('public holidays created', made)
