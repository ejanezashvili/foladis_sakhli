"""Hide / remove demo data left from the Odoo demo database (2026-11-08).

Archived (can be restored): demo contacts and companies, demo job positions, contact tags,
unused demo working schedules. Deleted: demo chat channels and demo messages in #general,
demo calendar meetings, demo activities, demo employee tags, demo work location.
Usage: python deploy/cleanup_demo.py <admin password>   (safe to re-run)
"""
import re
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE', 'active_test': False}


def xml_ids(module, model, pattern):
    rows = ex('ir.model.data', 'search_read', [[['module', '=', module], ['model', '=', model]]],
              {'fields': ['name', 'res_id']})
    return [r['res_id'] for r in rows if re.fullmatch(pattern, r['name'])]


def archive(model, ids, label):
    ids = ex(model, 'search', [[['id', 'in', ids], ['active', '=', True]]], {'context': C})
    if ids:
        ex(model, 'write', [ids, {'active': False}])
    print('archived', label, len(ids))


def delete(model, ids, label):
    ids = ex(model, 'search', [[['id', 'in', ids]]], {'context': C})
    if ids:
        ex(model, 'unlink', [ids])
    print('deleted', label, len(ids))


# contacts: demo companies/people from base + latin-named contacts without a login
# (work contacts of the deleted demo employees). Our people all have Georgian names.
demo_partners = xml_ids('base', 'res.partner', r'res_partner_\d+|res_partner_address_\d+|res_partner_main\d|partner_demo|partner_demo_portal')
keep = {1, 2, 3}  # company, OdooBot, admin
for p in ex('res.partner', 'search_read', [[['user_ids', '=', False]]], {'fields': ['name'], 'context': C}):
    if p['name'] and re.fullmatch(r"[A-Za-z .,&'()-]+", p['name']) and p['name'].lower() != 'test':
        demo_partners.append(p['id'])
archive('res.partner', [i for i in set(demo_partners) if i not in keep], 'contacts')

archive('hr.job', xml_ids('hr', 'hr.job', r'job_\w+'), 'job positions')
archive('res.partner.category', xml_ids('base', 'res.partner.category', r'res_partner_category_\d+'), 'contact tags')
archive('resource.calendar', [c for c in ex('resource.calendar', 'search', [[['id', '!=', 1]]], {'context': C})
                              if not ex('hr.employee', 'search_count', [[['resource_calendar_id', '=', c]]])], 'unused schedules')

# chat: keep #general and Administrators, drop the demo channels and demo posts in #general
general = xml_ids('mail', 'discuss.channel', r'channel_all_employees')[0]
admins = xml_ids('mail', 'discuss.channel', r'channel_admin')
delete('discuss.channel', ex('discuss.channel', 'search', [[['channel_type', '=', 'channel'], ['id', 'not in', [general] + admins]]],
                             {'context': C}), 'demo channels')
demo_authors = xml_ids('base', 'res.partner', r'partner_demo|partner_demo_portal')
demo_msgs = ex('mail.message', 'search', [[['model', '=', 'discuss.channel'], ['res_id', '=', general],
                                           ['author_id', 'in', demo_authors]]])
replies = ex('mail.message', 'search', [[['model', '=', 'discuss.channel'], ['res_id', '=', general],
                                         ['body', 'ilike', "Christine's office"]]])
delete('mail.message', demo_msgs + replies, 'demo posts in #general')

delete('calendar.event', xml_ids('calendar', 'calendar.event', r'calendar_event_\d+'), 'demo meetings')
delete('mail.activity', xml_ids('mail', 'mail.activity', r'mail_activity_demo_\w+'), 'demo activities')
delete('hr.employee.category', [c for c in xml_ids('hr', 'hr.employee.category', r'employee_category_\d+')
                                if not ex('hr.employee', 'search_count', [[['category_ids', 'in', c]]])], 'employee tags')
delete('hr.work.location', [w for w in xml_ids('hr', 'hr.work.location', r'work_location_\d+')
                            if not ex('hr.employee', 'search_count', [[['work_location_id', '=', w]]])], 'demo work location')
