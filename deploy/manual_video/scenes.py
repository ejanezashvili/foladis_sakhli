# -*- coding: utf-8 -*-
"""What the three manuals share: the demo department's ids, preparing and removing the demo tasks
(as the demo users themselves, with their own rights), and the moves every manual repeats."""
import datetime
from rec import Rec, rpc, MANAGER, EMPLOYEE, EMPLOYEE2

DEPT = 'სადემონსტრაციო განყოფილება'
ROLE_AUTHOR = ('დავალების ავტორი', '#7c3aed')
ROLE_EMPLOYEE = ('თანამშრომელი', '#2563eb')
ROLE_REVIEWER = ('ხელმძღვანელი / შემმოწმებელი', '#059669')
ALL = {'context': {'lang': 'ka_GE', 'tz': 'Asia/Tbilisi', 'active_test': False}}

_cache = {}


def project():
    if 'project' not in _cache:
        _cache['project'] = rpc(MANAGER, 'project.project', 'search', [[('name', '=', DEPT)]])[0]
    return _cache['project']


def uid(login):
    if login not in _cache:
        _cache[login] = rpc(login, 'res.users', 'search', [[('login', '=', login)]])[0]
    return _cache[login]


def stage(kind):
    if 'stages' not in _cache:
        ids = rpc(MANAGER, 'project.project', 'read', [[project()]], {'fields': ['type_ids']})[0]['type_ids']
        _cache['stages'] = {s['sh_kind']: s['id'] for s in rpc(MANAGER, 'project.task.type', 'read', [ids], {'fields': ['sh_kind']})}
    return _cache['stages'][kind]


def wipe():
    """Every demo task, template and welcome note of the demo users - the board empty again."""
    n = 0
    for _round in range(4):   # steps and sub-tasks first is not needed: whatever is left goes in the next round
        ids = rpc(MANAGER, 'project.task', 'search', [['|', ('project_id', '=', project()), ('create_uid', 'in', [uid(MANAGER), uid(EMPLOYEE), uid(EMPLOYEE2)])]], ALL)
        if not ids:
            break
        for tid in ids:
            try:
                rpc(MANAGER, 'project.task', 'unlink', [[tid]])
                n += 1
            except Exception as e:
                print('  not removed', tid, str(e)[:120])
    for login in (MANAGER, EMPLOYEE, EMPLOYEE2):
        ids = rpc(login, 'project.task', 'search', [[('project_id', '=', False), ('user_ids', 'in', [uid(login)])]], ALL)
        if ids:
            rpc(login, 'project.task', 'unlink', [ids])
            n += len(ids)
    print('wiped', n)


def when(days, hour=18):
    """A deadline `days` from today at `hour` Tbilisi time (stored in UTC)."""
    d = datetime.datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days)
    return (d - datetime.timedelta(hours=4)).strftime('%Y-%m-%d %H:%M:%S')


def task(name, assignee=EMPLOYEE, days=3, author=MANAGER, **vals):
    v = {'name': name, 'project_id': project(), 'sh_department_project_ids': [(6, 0, [project()])],
         'user_ids': [(6, 0, [uid(assignee)])], 'sh_responsible_id': uid(assignee), 'date_deadline': when(days)}
    v.update(vals)
    return rpc(author, 'project.task', 'create', [v])


def move(login, tid, kind):
    rpc(login, 'project.task', 'write', [[tid], {'stage_id': stage(kind)}])


def kind_of(tid):
    t = rpc(MANAGER, 'project.task', 'read', [[tid]], {'fields': ['stage_id']})[0]
    inv = {v: k for k, v in _cache.get('stages', {}).items()} or (stage('new') and {v: k for k, v in _cache['stages'].items()})
    return inv.get(t['stage_id'][0])


def until(tid, kinds, r, secs=12):
    """Waits until the task reaches one of the stage kinds (checked on the server)."""
    for _n in range(int(secs * 2)):
        if kind_of(tid) in kinds:
            return True
        r.wait(0.5)
    raise RuntimeError('task %s is %s, wanted %s' % (tid, kind_of(tid), kinds))


def sitting(name, login, role):
    """A logged-in browser with the role chip set; the login itself is cut from the video."""
    r = Rec(name)
    r.login(login)
    r.role(*role)
    return r


def open_task(r, tid, settle=2.5):
    r.goto('/odoo/project.task/%d' % tid, '.o_form_view', settle)


def stage_button(r, label):
    """The stage of that name on the form's stage bar (inside "..." when it is folded there)."""
    pg = r.pg
    btn = pg.locator('.o_form_view .o_statusbar_status button.o_arrow_button:visible', has_text=label)
    if btn.count():
        return btn
    more = pg.locator('.o_form_view .o_statusbar_status button.dropdown-toggle:visible')
    r.click(more, 0.5)
    return pg.locator('.o-dropdown--menu .dropdown-item:visible, .o_popover .dropdown-item:visible', has_text=label)


def form_top(r):
    """Scrolls the form back to its title."""
    r.pg.evaluate("""() => { for (const e of document.querySelectorAll('.o_form_view *')) { if (e.scrollTop > 0) e.scrollTo({top: 0, behavior: 'smooth'}); } }""")
    r.wait(0.9)


def pick_stage(r, label, after=2.0, modal=False):
    """Presses the stage of that name on the stage bar - straight, or inside "..." when it is folded there.
    modal: the stage opens a window (reason, final note) - waited for, and pressed once more when the
    line to the server dropped at that moment."""
    pg = r.pg
    for attempt in range(3):
        btn = pg.locator('.o_form_view .o_statusbar_status button.o_arrow_button:not(.dropdown-toggle):visible', has_text=label)
        if btn.count():
            r.click(btn, 1.0, 0.5)
        else:
            r.click(pg.locator('.o_form_view .o_statusbar_status button.dropdown-toggle:visible'), 0.6, 0.8)
            item = pg.locator('.o-dropdown--menu .dropdown-item:visible', has_text=label)
            item.first.wait_for(state='visible', timeout=8000)
            b = item.first.bounding_box()
            r.move(b['x'] + b['width'] / 2, b['y'] + b['height'] / 2)
            r.read(0.9)
            item.first.click()
        if not modal:
            break
        try:
            pg.wait_for_selector('.modal:visible', timeout=12000)
            break
        except Exception:
            print('  the window did not open, pressing again')
            pg.keyboard.press('Escape')
    r.wait(after)


def warm(r, tid, labels):
    """Before the recording starts: opens and closes the reason windows once, so that in the video
    they open at the first press (the first opening in a session can hang for a long time)."""
    open_task(r, tid)
    for label in labels:
        pick_stage(r, label, 1.0, modal=True)
        r.pg.locator('.modal:visible footer button, .modal:visible .modal-footer button', has_text='გაუქმება').last.click()
        r.wait(1.5)
