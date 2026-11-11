"""Delete Odoo demo records still left in the database (done 2026-11-10).

1. On the server, list the xml ids from the demo files of installed modules:
   python3 deploy/demo_scan.py <comma-separated installed modules> > ids.txt
2. Back up the database, then:  python deploy/cleanup_demo_2.py <admin password> ids.txt
Kept: company, admin user/partner, base groups, currencies, users' personal to-do stages.
Also set ir_module_module.demo = false (SQL) so new apps do not bring demo data again.
"""
import sys, collections, xmlrpc.client as x
sys.stdout.reconfigure(encoding='utf-8')
o = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: o.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
ids = [l.strip() for l in open(sys.argv[2], encoding='utf-8') if '.' in l and not l.startswith('[')]
byname = collections.defaultdict(set)
for i in ids:
    mod, name = i.split('.', 1); byname[mod].add(name)
found = []
for mod, names in byname.items():
    for r in ex('ir.model.data', 'search_read', [[['module', '=', mod], ['name', 'in', list(names)]]], {'fields': ['model', 'res_id', 'name', 'module']}):
        found.append(r)
bym = collections.defaultdict(list)
for r in found:
    bym[r['model']].append(r)
inv = {}
for model, rs in sorted(bym.items()):
    rid = [r['res_id'] for r in rs]
    try:
        live = ex(model, 'search_read', [[['id', 'in', rid]]], {'fields': ['display_name'], 'context': {'active_test': False, 'lang': 'ka_GE'}})
    except Exception as e:
        live = None
    if live is None:
        print(model, len(rid), 'ERR'); continue
    if not live: continue
    try:
        act = ex(model, 'search_count', [[['id', 'in', rid]]])
    except Exception:
        act = '?'
    inv[model] = [(l['id'], l['display_name']) for l in live]
    # print(f'{model}: {len(live)} (active {act}) e.g. ' + '; '.join(str(l['display_name'])[:30] for l in live[:4]))

C = {'active_test': False}
KEEP_MODELS = {'res.company', 'res.groups', 'res.currency', 'project.task.type', 'account.analytic.plan'}
KEEP = {('res.users', 2), ('res.partner', 3)}
# children first
ORDER = ['mailing.trace', 'mailing.subscription', 'mailing.mailing', 'mailing.contact', 'mailing.list',
         'survey.user_input.line', 'survey.user_input', 'survey.question.answer', 'survey.question', 'survey.survey',
         'gamification.karma.tracking', 'gamification.badge', 'gamification.karma.rank',
         'mail.notification', 'mail.message', 'mail.blacklist', 'mail.canned.response', 'mail.guest', 'ir.attachment',
         'sms.template', 'utm.campaign', 'utm.source', 'utm.stage', 'calendar.filters', 'calendar.event.type',
         'hr.job.skill', 'hr.skill.level', 'hr.skill', 'hr.skill.type', 'hr.resume.line.type',
         'hr.version', 'hr.job', 'resource.calendar', 'project.project.stage', 'mail.template',
         'account.analytic.account', 'res.partner.bank', 'res.bank', 'res.currency.rate',
         'res.partner.category', 'res.users', 'res.partner']
orphan_versions = ex('hr.version', 'search', [[['employee_id', '=', False]]], {'context': C})
fails = []
for model in ORDER + [m for m in inv if m not in ORDER]:
    if model in KEEP_MODELS:
        continue
    ids = [i for i, _ in inv.get(model, []) if (model, i) not in KEEP]
    if model == 'hr.version':
        ids = sorted(set(ids) | set(orphan_versions))
    ids = ex(model, 'search', [[['id', 'in', ids]]], {'context': C}) if ids else []
    if not ids:
        continue
    try:
        ex(model, 'unlink', [ids], {'context': C})
        print(f'{model}: deleted {len(ids)}')
    except Exception:
        ok = 0
        for i in ids:
            try:
                ex(model, 'unlink', [[i]], {'context': C})
                ok += 1
            except Exception as e:
                msg = str(e).strip().split('\n')
                fails.append((model, i, msg[-1][:150]))
        print(f'{model}: deleted {ok}/{len(ids)}')
# demo analytic plans (departments, internal) once their accounts are gone
for pid in (2, 3):
    try:
        if not ex('account.analytic.account', 'search_count', [[['plan_id', 'child_of', pid]]], {'context': C}):
            ex('account.analytic.plan', 'unlink', [[pid]])
            print('analytic plan deleted', pid)
    except Exception as e:
        fails.append(('account.analytic.plan', pid, str(e).strip().split('\n')[-1][:150]))
print('FAILED', len(fails))
for f in fails:
    print(' ', f)
