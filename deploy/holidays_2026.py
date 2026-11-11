"""Georgian public holidays of 2026 (January - October; 23 November is already in setup_automation_rules_2.py).
They show in the time off calendar and its "Public Holidays" list, and count as non-working days.
Usage: python deploy/holidays_2026.py <admin password>   (safe to re-run)
"""
import datetime as dt
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)

# Orthodox Easter 2026: 12 April
HOLIDAYS = [
    ('2026-01-01', 'ახალი წელი'), ('2026-01-02', 'ახალი წელი'), ('2026-01-07', 'შობა'),
    ('2026-01-19', 'ნათლისღება'), ('2026-03-03', 'დედის დღე'), ('2026-03-08', 'ქალთა საერთაშორისო დღე'),
    ('2026-04-09', 'ეროვნული ერთიანობის დღე'), ('2026-04-10', 'დიდი პარასკევი'), ('2026-04-11', 'დიდი შაბათი'),
    ('2026-04-12', 'აღდგომა'), ('2026-04-13', 'აღდგომის ორშაბათი'), ('2026-05-09', 'ფაშიზმზე გამარჯვების დღე'),
    ('2026-05-12', 'წმ. ანდრია პირველწოდებულის დღე'), ('2026-05-17', 'ოჯახის სიწმინდის დღე'),
    ('2026-05-26', 'დამოუკიდებლობის დღე'), ('2026-08-28', 'მარიამობა'), ('2026-10-14', 'სვეტიცხოვლობა'),
]
made = 0
for day, label in HOLIDAYS:
    d = dt.datetime.strptime(day, '%Y-%m-%d')
    # Tbilisi time = UTC+4: the whole local day
    start = (d - dt.timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')
    end = (d + dt.timedelta(hours=19, minutes=59, seconds=59)).strftime('%Y-%m-%d %H:%M:%S')
    if ex('resource.calendar.leaves', 'search_count', [[['resource_id', '=', False], ['date_from', '=', start]]]):
        continue
    ex('resource.calendar.leaves', 'create', [{'name': label, 'date_from': start, 'date_to': end,
                                               'company_id': 1, 'calendar_id': False, 'time_type': 'leave'}])
    made += 1
print('public holidays 2026 created', made)
