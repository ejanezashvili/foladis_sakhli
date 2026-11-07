"""Build the position structure from the company org chart (Docs: ფოლადის სახლი _ ტრუქტურა.pdf).

Rule: a chart box that has people under it becomes a sub-department (its holder = head);
a leaf box becomes a job position (hr.job) in its department. Existing employees are
linked to their position (their own job title text is kept). Every new sub-department
gets a project with the same settings as its parent department's project.
Afterwards each employee's direct manager is recomputed from the department heads.

Usage: python deploy/setup_structure.py <admin password>
Safe to re-run: existing sub-departments / positions are reused.
"""
import sys
import xmlrpc.client as x

sys.stdout.reconfigure(encoding='utf-8')
m = x.ServerProxy('http://146.255.249.126/xmlrpc/2/object', allow_none=True)
ex = lambda *a, **k: m.execute_kw('steelhouse', 2, sys.argv[1], *a, **k)
C = {'lang': 'ka_GE'}
ROOT = 'ფოლადის სახლი'

# new sub-departments: (parent path, name, head employee ids, head position title)
SUBDEPTS = [
    ('ადმინისტრაცია', 'ოფის მენეჯერი', [27], 'ოფის მენეჯერი'),
    ('იურიდიული დეპარტამენტი', 'შიდა იურისტი', [24], 'შიდა იურისტი'),
    ('იურიდიული დეპარტამენტი', 'გარე იურისტი', [], 'გარე იურისტი'),
    ('ფინანსების დეპარტამენტი / ბუღალტერია', 'მთავარი ბუღალტრები', [38, 36, 35, 37], 'მთავარი ბუღალტერი'),
    ('ბრენდმენეჯმენტის განყოფილება', 'ბრენდ მენეჯერები', [108, 96, 95, 98], 'ბრენდ მენეჯერი'),
    ('ლოჯისტიკა / ფილიალი / საწყობი და ინვენტარიზაცია', 'საწყობის მენეჯერი', [], 'საწყობის მენეჯერი'),
    ('ბადეების საწარმო / წარმოება', 'ოპერატორი', [], 'ოპერატორი'),
    ('სახურავების საწარმო / წარმოება', 'ოპერატორი', [], 'ოპერატორი'),
]

# vacant heads: show which position is missing
HEAD_TITLES = {
    'ლოჯისტიკა / ფილიალი / საწყობი და ინვენტარიზაცია': 'საწყობის და ინვენტარიზაციის ხელმძღვანელი',
    'კვადრატულების საწარმო / წარმოება / მზა პროდუქციის საწყობი': 'საწყობის მენეჯერი',
    'კვადრატულების საწარმო / წარმოება / საწარმოო საწყობი': 'დანადგარის ოპერატორი',
    'ნადირულის მეურნეობა': 'მენეჯერი',
}

# positions: department path -> [(position, [employee ids])]
JOBS = {
    'ადმინისტრაცია': [('HR მენეჯერი', [26]), ('შიდა უსაფრთხოების მენეჯერი', [28])],
    'ადმინისტრაცია / ოფის მენეჯერი': [('მზარეული', []), ('დიასახლისი', [])],
    'იურიდიული დეპარტამენტი / შიდა იურისტი': [('ასისტენტი', [])],
    'იურიდიული დეპარტამენტი / გარე იურისტი': [('იურისტი', [])],
    'მარკეტინგი': [('მარკეტოლოგი', [46])],
    'ფინანსების დეპარტამენტი / ანალიტიკა': [('ანალიტიკოსი', [42, 43])],
    'ფინანსების დეპარტამენტი / ბუღალტერია': [('მოლარე', [83, 82])],
    'ფინანსების დეპარტამენტი / ბუღალტერია / მთავარი ბუღალტრები': [('ბუღალტრის ასისტენტი', [39, 40])],
    'გაყიდვების განყოფილება': [('განყოფილების მენეჯერი', [71, 66, 73, 67, 63, 74, 64, 61, 65, 75, 69, 70, 62, 72, 68])],
    'ტენდერების გაყიდვები': [('სპეციალისტი', [78])],
    'Call ცენტრის გაყიდვები': [('ოპერატორი', [49, 52, 51, 48, 53, 56, 54, 57, 50, 47, 55, 58])],
    'ბრენდმენეჯმენტის განყოფილება / ბრენდ მენეჯერები': [('ასისტენტი', [99, 97])],
    'ლოჯისტიკა': [('ლოჯისტიკის ოპერატორი', [80, 81])],
    'ლოჯისტიკა / ავტოპარკი': [('მექანიკოსი', []), ('ხელოსანი', []), ('სპეც ტექნიკის ოპერატორი', []),
                              ('მძღოლი', []), ('დარაჯი', [])],
    'ლოჯისტიკა / ფილიალი / საწყობი და ინვენტარიზაცია / საწყობის მენეჯერი': [('ოპერატორი', [])],
    'ლოჯისტიკა / ფილიალი / საცალო გაყიდვები და სერვისი': [('სერვის მენეჯერი', [85, 84, 86, 88, 119, 87])],
    'საბაჟო': [('საბაჟო დეკლარანტი', [116])],
    # which assistant is where is not in the list - to be confirmed by the company
    'კვადრატულების საწარმო / ბრენდის განყოფილება': [('ასისტენტი', [107])],
    'კვადრატულების საწარმო / კომერციული მიმართულება': [('ასისტენტი', [109])],
    'კვადრატულების საწარმო / წარმოება / მზა პროდუქციის საწყობი': [('მუშა', [])],
    'კვადრატულების საწარმო / წარმოება / საწარმოო საწყობი': [('საწარმო მუშა', [])],
    'ბადეების საწარმო / კომერციული მიმართულება': [('ასისტენტი', [102])],
    'ბადეების საწარმო / წარმოება / ოპერატორი': [('მუშა', [])],
    'სახურავების საწარმო / კომერციული მიმართულება': [('ასისტენტი', [92]), ('ოპერატორი', [94, 93])],
    'სახურავების საწარმო / წარმოება / ოპერატორი': [('მუშა', [])],
    'ქონსტრაქშენის ცეხი / ბრენდის განყოფილება': [('ასისტენტი', [])],
    'ქონსტრაქშენის ცეხი / წარმოება / რკინა': [('ხარატი', []), ('ოპერატორი', []), ('შემდუღებელი', []), ('მუშა', [])],
    'ქონსტრაქშენის ცეხი / წარმოება / კარ-ფანჯარა': [('ხარატი', []), ('ოპერატორი', []), ('მუშა', [])],
    'ბალასტი': [('კონსულტანტი', [])],
    'საქფაქტორი': [('საოპერაციო მენეჯერი', []), ('სერვის მენეჯერი', [])],
}

PROJECT_FIELDS = ['privacy_visibility', 'user_id', 'type_ids', 'task_properties_definition',
                  'allow_recurring_tasks', 'allow_task_dependencies', 'allow_milestones',
                  'label_tasks', 'resource_calendar_id']


def depts():
    return {d['complete_name']: d['id'] for d in ex('hr.department', 'search_read', [[]],
                                                       {'fields': ['complete_name'], 'context': C})}


def dept_id(path):
    return depts()[ROOT + ' / ' + path]


def copy_project(parent_path, path):
    name = path
    if ex('project.project', 'search_count', [[['name', '=', name]]], {'context': C}):
        return
    src = ex('project.project', 'search', [[['name', '=', parent_path]]], {'context': C})
    vals = {'name': name}
    if src:
        p = ex('project.project', 'read', [src[:1]], {'fields': PROJECT_FIELDS})[0]
        for k in PROJECT_FIELDS:
            v = p[k]
            if k == 'type_ids':
                vals[k] = [(6, 0, v)]
            elif isinstance(v, list) and len(v) == 2 and isinstance(v[0], int) and k in ('user_id', 'resource_calendar_id'):
                vals[k] = v[0]
            else:
                vals[k] = v
    pid = ex('project.project', 'create', [vals], {'context': {'lang': 'ka_GE'}})
    print('  project', pid, name)


HAS_TITLE = 'sh_head_title' in ex('hr.department', 'fields_get', [], {'attributes': ['type']})
if not HAS_TITLE:
    print('note: steelhouse_hr 19.0.1.7+ not installed yet - head titles skipped, re-run after upgrade')

# 1) sub-departments (+ heads move into them) and their projects
for parent, name, heads, title in SUBDEPTS:
    pid = dept_id(parent)
    found = ex('hr.department', 'search', [[['name', '=', name], ['parent_id', '=', pid]]])
    vals = {'manager_ids': [(6, 0, heads)]}
    if HAS_TITLE:
        vals['sh_head_title'] = title
    if found:
        did = found[0]
        ex('hr.department', 'write', [[did], vals])
    else:
        did = ex('hr.department', 'create', [dict(vals, name=name, parent_id=pid)])
        print('dept', did, parent + ' / ' + name)
    if heads:
        ex('hr.employee', 'write', [heads, {'department_id': did}])
    copy_project(parent, parent + ' / ' + name)

for path, title in (HEAD_TITLES.items() if HAS_TITLE else []):
    ex('hr.department', 'write', [[dept_id(path)], {'sh_head_title': title}])

# 2) positions; employees are linked to them (and moved into that department), job title text kept
all_depts = depts()
for path, jobs in JOBS.items():
    did = all_depts[ROOT + ' / ' + path]
    for seq, (job_name, emp_ids) in enumerate(jobs, 1):
        found = ex('hr.job', 'search', [[['name', '=', job_name], ['department_id', '=', did]]], {'context': C})
        jid = found[0] if found else ex('hr.job', 'create', [{'name': job_name, 'department_id': did, 'sequence': seq,
                                                             'no_of_recruitment': 0}], {'context': {'lang': 'ka_GE'}})
        for e in ex('hr.employee', 'read', [emp_ids], {'fields': ['job_title']}):
            ex('hr.employee', 'write', [[e['id']], {'department_id': did, 'job_id': jid, 'job_title': e['job_title']}])
    print('positions', path, len(jobs))

# 3) direct managers from department heads (own department, else the nearest head above)
D = {d['id']: d for d in ex('hr.department', 'search_read', [[]], {'fields': ['manager_ids', 'parent_id']})}
changed = 0
for e in ex('hr.employee', 'search_read', [[]], {'fields': ['department_id', 'parent_id']}):
    if not e['department_id']:
        continue
    d = D[e['department_id'][0]]
    while (not d['manager_ids'] or e['id'] in d['manager_ids']) and d['parent_id']:
        d = D[d['parent_id'][0]]
    mgr = ex('hr.department', 'read', [[d['id']]], {'fields': ['manager_id']})[0]['manager_id']
    mgr = mgr and mgr[0]
    if mgr == e['id']:
        mgr = False
    if (e['parent_id'] and e['parent_id'][0]) != mgr:
        ex('hr.employee', 'write', [[e['id']], {'parent_id': mgr or False}])
        changed += 1
print('direct managers changed', changed)
