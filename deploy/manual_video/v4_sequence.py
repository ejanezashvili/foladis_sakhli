# -*- coding: utf-8 -*-
"""Video manual 4 - a sequence with parallel steps: how it looks on the board and on a step card
(one's own steps in bold), moving a step, opening the other steps, a photo on a step, and a step
that waits for a previous one that is on hold (asking, and the permission to start).
    run.ps1 v4_sequence.py [-Fast]"""
import datetime
import os
import scenes as s
from rec import Rec, rpc, join, WORK, MANAGER, EMPLOYEE, EMPLOYEE2
from v2_create import add_step

T_MAIN = 'მაღაზიის ფასადის მონტაჟი'
S1 = 'ობიექტის აზომვა'
S2 = 'მასალის დაჭრა საამქროში'
S3 = 'ტრანსპორტის დაჯავშნა'
S4 = 'ობიექტის მომზადება მონტაჟისთვის'
T_WARM = 'კლიენტთან შეხვედრის ოქმი'
HOLD_REASON = 'სატრანსპორტო კომპანია პასუხს ხვალ მოგვცემს.'
# the step diagram of static/src/task_chain/task_chain.js
COL0, COL, CARD_W, GAP = 182, 310, 236, 74


def day(days):
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def step(main, direction, anchor, name, who, days):
    return rpc(MANAGER, 'project.task', 'sh_chain_create', [[main], direction, {
        'name': name, 'project_id': s.project(), 'user_id': s.uid(who), 'reviewer_ids': [s.uid(MANAGER)],
        'deadline': day(days)}, anchor])


def prepare():
    s.wipe()
    s.task('მომწოდებელთან ხელშეკრულების გადახედვა', assignee=EMPLOYEE2, days=6)
    warm = s.task(T_WARM, days=5)
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[warm]])
    s.move(EMPLOYEE, warm, 'in_progress')
    main = s.task(T_MAIN, assignee=MANAGER, days=9, priority='2', description=(
        '<p>მაღაზიის ფასადის მონტაჟი: აზომვა, მასალის მომზადება, ტრანსპორტი და ობიექტის მომზადება.</p>'))
    # the same calls the "თანმიმდევრობა" tab makes: the first step before the main task, the others after the last step
    s1 = step(main, 'prev', main, S1, EMPLOYEE, 2)
    s2 = step(main, 'between', s1, S2, EMPLOYEE2, 4)
    s3 = step(main, 'between', s2, S3, EMPLOYEE, 4)
    s4 = step(main, 'between', s3, S4, EMPLOYEE2, 7)
    return {'main': main, 's1': s1, 's2': s2, 's3': s3, 's4': s4, 'warm': warm}


def find(name):
    return rpc(MANAGER, 'project.task', 'search', [[('name', '=', name), ('project_id', '=', s.project())]])[0]


def demo_photo():
    """The "photo" the employee attaches: a drawn measuring sheet of the facade."""
    path = os.path.join(WORK, 'ფასადის აზომვა.jpg')
    r = Rec('photo', video=False)
    r.pg.set_viewport_size({'width': 900, 'height': 600})
    r.pg.set_content("""<html><body style="margin:0;background:#e8e2d5;font-family:Segoe UI,Sylfaen">
      <svg width="900" height="600" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="430" width="900" height="170" fill="#b9b3a4"/>
        <rect x="150" y="130" width="600" height="300" fill="#f6f3ec" stroke="#3b3b3b" stroke-width="4"/>
        <rect x="150" y="130" width="600" height="60" fill="#c9792b" stroke="#3b3b3b" stroke-width="4"/>
        <rect x="200" y="230" width="210" height="200" fill="#9fc3d8" stroke="#3b3b3b" stroke-width="4"/>
        <rect x="470" y="230" width="230" height="150" fill="#9fc3d8" stroke="#3b3b3b" stroke-width="4"/>
        <g stroke="#c0392b" stroke-width="3" fill="none">
          <path d="M150 95 H750 M150 80 V110 M750 80 V110"/><path d="M790 130 V430 M775 130 H805 M775 430 H805"/>
        </g>
        <g fill="#c0392b" font-size="30" font-weight="700">
          <text x="405" y="78">12.40 მ</text><text x="812" y="290">3.20 მ</text>
        </g>
        <text x="30" y="570" font-size="26" fill="#3b3b3b">ფასადის აზომვა - ობიექტი</text>
      </svg></body></html>""")
    r.pg.screenshot(path=path, type='jpeg', quality=88)
    r.close()
    return path


def card(r, name):
    """The card with that title (a step's name also stands in the other steps' "next / previous" lines)."""
    return r.pg.locator('.o_kanban_record').filter(has=r.pg.locator('.o_sh_card_title', has_text=name))


def chain_card(r, name):
    return r.pg.locator('.o_sh_chain_card', has_text=name)


def chain_tab(r):
    r.click(r.pg.locator('.o_form_view .nav-tabs .nav-link', has_text='თანმიმდევრობა'), 1.0, 2.5)
    r.pg.wait_for_selector('.o_sh_chain_card')
    show_steps(r)


def show_steps(r):
    """The whole step diagram in the middle of the window."""
    r.pg.locator('.o_sh_chain_scroll').first.evaluate("e => { e.scrollTo({left: 0}); e.scrollIntoView({block: 'center', behavior: 'smooth'}); }")
    r.wait(1.0)


def move_step(r, main, name, level, mode, lands):
    """Drags the step's card onto step `level` (it joins the step) or into the gap before it (a new step
    there); `lands` - the column it must end up in."""
    show_steps(r)

    def target():
        b = r.pg.locator('.o_sh_chain_canvas').first.bounding_box()
        return b['x'] + COL0 + COL * level + (CARD_W / 2 if mode == 'into' else -GAP / 2), b['y'] + 110

    r.drag(chain_card(r, name).locator('.o_sh_chain_name'), target)
    for _n in range(30):
        if levels(main).get(name) == lands:
            break
        r.wait(0.5)
    else:
        raise RuntimeError('%s is on step %s, wanted %s' % (name, levels(main).get(name), lands))
    r.wait(1.5)
    show_steps(r)


def tidy(t):
    """After the moves: the arrows must be the planned ones again. Taking a step out of the middle joins its
    previous step straight to the next one, and that arrow stays when the step is put back - removed here,
    as the "x" on the arrow does."""
    def prev(tid):
        return set(rpc(MANAGER, 'project.task', 'read', [[tid]], {'fields': ['depend_on_ids']})[0]['depend_on_ids'])

    if t['s1'] in prev(t['main']):      # before 19.0.1.177.0 the move left this arrow behind
        print('  an arrow over the moved step was left - removed')
        rpc(MANAGER, 'project.task', 'sh_chain_unlink_edge', [[t['main']], t['s1'], t['main']])
    want = {'main': {t['s4']}, 's4': {t['s2'], t['s3']}, 's3': {t['s1']}, 's2': {t['s1']}, 's1': set()}
    got = {k: prev(t[k]) for k in want}
    if got != want:
        raise RuntimeError('the sequence is not the planned one: %s, wanted %s' % (got, want))


def levels(main):
    """{step name: column} as the tab shows it."""
    data = rpc(MANAGER, 'project.task', 'sh_chain_data', [[main]])
    return {n['name']: n['level'] for n in data['nodes']}


def sit(name, login, role, play, *args):
    r = s.sitting(name, login, role)
    try:
        play(r, *args)
        return r.close()
    except Exception:
        print('FAILED at', r.pg.url, '| screenshot:', r.shot('FAILED'))
        r.close()
        raise


# ---------------------------------------------------------------- 1: the author
def author(r, t):
    pg = r.pg
    r.goto('/odoo/project', '.o_kanban_record', 1.5)
    r.title('თანმიმდევრობა და პარალელური დავალებები', 'როგორ ჩანს ნაბიჯები დაფაზე, როგორ გადავაადგილო ნაბიჯი,\n'
            'როგორ ავტვირთო ფოტო და რა ხდება, როცა წინა ნაბიჯი ჩერდება', 0.5)
    r.mark_start()
    r.read(6)
    r.untitle()

    # the board: only the main task
    r.click(pg.locator('.o_kanban_record', has_text=s.DEPT), 1.0, 3.5)
    pg.wait_for_selector('.o_kanban_group')
    r.point(card(r, T_MAIN), 1.5)
    r.cap('ეს არის დეპარტამენტის დაფა: „პროექტი“ → დეპარტამენტი. სვეტები: ახალი, მუშავდება, შემოწმებაზე, დასრულებული.')
    r.cap('დიდი დავალება ნაბიჯებად იყოფა. ამ დაფაზე ჩანს მხოლოდ მთავარი დავალება - ნაბიჯების ბარათებს ხედავს მხოლოდ მათი შემსრულებელი.')
    r.cap('ბარათზე წერია „თანმიმდევრობა 0/4“: ოთხი ნაბიჯიდან ჯერ არც ერთი დასრულებულა. დააჭირეთ მას.')
    r.click(card(r, T_MAIN).locator('.o_sh_cl_btn'), 1.0, 2.0)
    pg.wait_for_selector('.o_sh_cl_item')
    r.point(card(r, T_MAIN).locator('.o_sh_cl_list'), 1.5)
    r.cap('სია იხსნება ბარათშივე: ნაბიჯები რიგის მიხედვით და თითოეულის მდგომარეობა. „ელოდება“ ნიშნავს, რომ წინა ნაბიჯი ჯერ არ დასრულებულა.')

    # the tab
    r.cap('სრული სურათის სანახავად გახსენით მთავარი დავალება და გადადით ჩანართზე „თანმიმდევრობა“.')
    r.click(card(r, T_MAIN).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    chain_tab(r)
    r.point(pg.locator('.o_sh_chain_mainbar'), 1.3)
    r.cap('ზემოთ - მთავარი დავალება და რამდენი ნაბიჯია შესრულებული. ქვემოთ - ნაბიჯები მარცხნიდან მარჯვნივ, ისრებით.')
    r.point(chain_card(r, S1), 1.3)
    r.cap('თითო ბარათი ცალკე დავალებაა: სახელი, დეპარტამენტი, პასუხისმგებელი და ვადა. პირველი ნაბიჯი აქტიურია.')
    r.point(chain_card(r, S2), 1.3)
    r.cap('დანარჩენს ბოქლომი ადევს: ნაბიჯი იწყება მხოლოდ მაშინ, როცა წინა დასრულდება და შემმოწმებელი დაადასტურებს.')

    # two steps at the same time: the card is dragged under the other one
    r.cap('ორი საქმე ერთდროულადაც შეიძლება კეთდებოდეს. მაშინ ისინი ერთ ნაბიჯში დგას, ერთმანეთის ქვემოთ.')
    r.cap('ტრანსპორტის დაჯავშნას მასალის დაჭრის დასრულება არ სჭირდება. გადაათრიეთ მისი ბარათი მეორე ნაბიჯის სვეტზე.')
    move_step(r, t['main'], S3, 1, 'into', 1)
    r.point(chain_card(r, S3), 1.5)
    r.cap('ბარათი მეორე ნაბიჯში ჩაჯდა, მასალის დაჭრის ქვემოთ. ორივე ერთდროულად დაიწყება, როცა პირველი ნაბიჯი დასრულდება.')
    r.point(chain_card(r, S4), 1.3)
    r.cap('შემდეგი ნაბიჯი ელოდება ორივეს: სანამ ორივე დავალება არ დასრულდება, ის არ დაიწყება.')
    r.cap('ასევე „იხსნება“ ნაბიჯი, რომელიც ტყუილად ელოდება სხვას. უკან დასაბრუნებლად ბარათი გადაათრიეთ ნაბიჯებს შორის - ცალკე ნაბიჯი გახდება.')

    # opening a step
    r.cap('ნაბიჯის გასახსნელად დააჭირეთ ბარათს: პატარა ფანჯარაში იცვლება სახელი, პასუხისმგებელი და ვადა.')
    r.click(chain_card(r, S1).locator('.o_sh_chain_name'), 1.0, 2.0)
    pop = pg.locator('.o_sh_chain_pop')
    pop.wait_for(state='visible', timeout=15000)
    r.point(pop.locator('a', has_text='დავალების სრულად გახსნა'), 1.2)
    r.cap('„დავალების სრულად გახსნა“ ხსნის ამ ნაბიჯის მთელ დავალებას - აღწერით, ფაილებით და მიმოწერით.')
    r.click(pop.locator('a', has_text='დავალების სრულად გახსნა'), 0.8, 3.5)
    pg.wait_for_selector('.modal .o_form_view')
    r.cap('ნაბიჯი იხსნება დიდ ფანჯარაში, თანმიმდევრობიდან გაუსვლელად. დახურვის შემდეგ ისევ ნაბიჯებზე ბრუნდებით.')
    r.click(pg.locator('.modal header .btn-close, .modal .modal-header .btn-close'), 0.8, 2.0)


# ---------------------------------------------------------------- 2: the first performer
def nino_work(r, t, photo):
    pg = r.pg
    s.warm(r, t['warm'], ('შეჩერებული',))
    rpc(MANAGER, 'project.task', 'unlink', [[t['warm']]])      # only the steps stay on her board
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.mark_start()
    r.cap('ახლა - ნაბიჯის შემსრულებლის ეკრანი: „დავალებები“ → „ჩემი დავალებები“. აქ სვეტები სხვაა: დღეს, ეს კვირა, ეს თვე.')
    r.point(card(r, S1).locator('.o_sh_step_badge'), 1.5)
    r.cap('ნაბიჯების ბარათები მხოლოდ აქ ჩანს და მხოლოდ შემსრულებელს; ადმინისტრატორი და ავტორი მათ დაფაზე ვერ ხედავს. ბარათზე წერია: „ნაბიჯი 1/4 - შენი ჯერია“ და ვინ არის შემდეგი.')
    r.point(card(r, S3).locator('.o_sh_step_badge'), 1.5)
    r.cap('მეორე ბარათი: „ნაბიჯი 3/4 - ელოდება წინა ნაბიჯს“. ქვემოთ წერია, რომელ ნაბიჯს ელოდება, ვინ ასრულებს და რა სტადიაზეა.')
    r.cap('მთელი თანმიმდევრობის სანახავად დააჭირეთ „თანმიმდევრობა“-ს ბარათზე.')
    r.click(card(r, S3).locator('.o_sh_cl_btn'), 1.0, 2.0)
    pg.wait_for_selector('.o_sh_cl_item')
    r.point(card(r, S3).locator('.o_sh_cl_mine').first, 1.5)
    r.cap('ჩანს ყველა ნაბიჯი. მუქი ლურჯი შრიფტით გამოყოფილია ის ნაბიჯები, სადაც თქვენ ხართ შემსრულებელი.')
    r.cap('სიაში ნაბიჯის სახელზე დაჭერით ის დავალება იხსნება. გავხსნათ ჩვენი პირველი ნაბიჯი.')
    r.click(card(r, S3).locator('.o_sh_cl_item', has_text=S1).locator('.o_sh_cl_name'), 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')

    # the step itself
    chain_tab(r)
    r.point(pg.locator('.o_sh_chain_card.o_sh_current'), 1.5)
    r.cap('დავალების ჩანართში „თანმიმდევრობა“ თქვენი ნაბიჯი ჩარჩოთია გამოყოფილი - ჩანს, რა არის მანამდე და რა მოჰყვება.')
    s.form_top(r)
    r.click(pg.locator('button[name="action_sh_accept"]:visible'), 1.0, 1.5)
    s.until(t['s1'], ('accepted',), r)
    s.pick_stage(r, 'მიმდინარე', 1.5)
    s.until(t['s1'], ('in_progress',), r)
    r.cap('ნაბიჯი ჩვეულებრივი დავალებაა: „მიღება“, შემდეგ „მიმდინარე“.')

    # the photo
    r.cap('ფოტოს ასატვირთად მარჯვნივ დააჭირეთ „შიდა შენიშვნა“-ს, შემდეგ კი ქაღალდის სამაგრს.')
    r.click(pg.locator('.o-mail-Chatter button', has_text='შიდა შენიშვნა'), 0.8, 1.2)
    r.type(pg.locator('textarea.o-mail-Composer-input'), 'აზომვა დასრულებულია, ფოტო თან ერთვის.')
    with pg.expect_file_chooser() as fc:
        r.click(pg.locator('.o-mail-Composer button[name="upload-files"]'), 0.8, 0.5)
    fc.value.set_files(photo)
    r.wait(3.0)
    r.cap('აირჩიეთ ფოტო კომპიუტერიდან ან ტელეფონიდან. რამდენიმე ფოტოს ერთად ატვირთვაც შეიძლება.')
    r.click(pg.locator('button.o-mail-Composer-send'), 0.8, 3.0)
    r.point(pg.locator('.o-mail-Message').first, 1.5)
    r.cap('ფოტო დავალებაზე შეინახა. მას ხედავს შემმოწმებელიც - დადასტურებისას ფოტო მის წინაშე იქნება.')
    r.click(pg.locator('button[name="action_sh_mark_done"]:visible'), 1.0, 1.5)
    pg.wait_for_selector('.modal:visible')
    r.click(pg.locator('.modal button:visible', has_text='კი, შესრულდა'), 1.0, 1.5)
    s.until(t['s1'], ('review',), r)
    r.read(1.5)
    r.cap('„შესრულებულია“ - ნაბიჯი შემოწმებაზე გადავიდა. შემდეგი ნაბიჯი გაიხსნება, როცა შემმოწმებელი დაადასტურებს.')

    # meanwhile: the reviewer confirms step 1, the other parallel task is done and confirmed
    rpc(MANAGER, 'project.task', 'sh_approval_approve', [[t['s1']]])
    rpc(EMPLOYEE2, 'project.task', 'action_sh_accept', [[t['s2']]])
    rpc(EMPLOYEE2, 'project.task', 'action_sh_mark_done', [[t['s2']]])
    rpc(MANAGER, 'project.task', 'sh_approval_approve', [[t['s2']]])

    # the parallel task opened; it gets stuck
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.5)
    r.point(card(r, S3).locator('.o_sh_step_badge'), 1.5)
    r.cap('შემმოწმებელმა პირველი ნაბიჯი დაადასტურა. „ტრანსპორტის დაჯავშნაზე“ ახლა წერია „შენი ჯერია“ - მოვიდა შეტყობინებაც.')
    r.click(card(r, S3).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.click(pg.locator('button[name="action_sh_accept"]:visible'), 1.0, 1.5)
    s.until(t['s3'], ('accepted',), r)
    r.cap('ვიღებთ დავალებას. მაგრამ დავუშვათ, მისი დასრულება ახლა შეუძლებელია - ველოდებით სხვის პასუხს.')
    r.cap('ასეთ დროს დავალება არ დატოვოთ „მიმდინარეში“: გადაიყვანეთ „შეჩერებულზე“ და მიუთითეთ მიზეზი.')
    s.pick_stage(r, 'შეჩერებული', 2.0, modal=True)
    pg.wait_for_selector('.modal:visible')
    r.type(pg.locator('.modal textarea:visible'), HOLD_REASON)
    r.click(pg.locator('.modal button[name="action_confirm"]:visible'), 1.0, 2.5)
    s.until(t['s3'], ('on_hold',), r)
    r.read(1.5)
    r.cap('დავალება შეჩერდა. შემდეგი ნაბიჯის შემსრულებელმა მიიღო შეტყობინება, რომ მისი წინა დავალება შეჩერებულია.')


# ---------------------------------------------------------------- 3: the one who waits
def luka_waits(r, t):
    pg = r.pg
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.mark_start()
    r.cap('ახლა - შემდეგი ნაბიჯის შემსრულებელი. მისი წინა ორი დავალებიდან ერთი დასრულდა, მეორე კი შეჩერებულია.')
    r.point(card(r, S4).locator('.o_sh_held_strip'), 1.5)
    r.cap('ბარათზე წერია: „წინა დავალება შეჩერებულია - დაიწყება მხოლოდ წინა დავალების ნებართვით“.')
    r.click(card(r, S4).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.point(pg.locator('.o_form_view .alert-warning:visible').first, 1.8)
    r.cap('დავალების თავში ჩანს, რომელი დავალებაა შეჩერებული და რა მიზეზით. ღილაკი „მიღება“ ჯერ არ არის - დაწყება არ შეიძლება.')
    r.cap('ნებართვას იძლევა შეჩერებული დავალების შემსრულებელი, პასუხისმგებელი ან შემმოწმებელი. სთხოვეთ მათ ღილაკით „დაწყების მოთხოვნა“.')
    btn = pg.locator('.o_form_view button[name="action_sh_request_start"]:visible')
    r.click(btn, 1.2, 2.5)
    for _n in range(30):
        if rpc(MANAGER, 'project.task', 'read', [[t['s4']]], {'fields': ['sh_start_request_date']})[0]['sh_start_request_date']:
            break
        r.wait(0.5)
    else:
        raise RuntimeError('the request was not sent')
    r.point(pg.locator('.o_form_view .o_sh_start_request'), 1.5)
    r.cap('მოთხოვნა გაიგზავნა: წინა დავალების შემსრულებელმა და შემმოწმებელმა მიიღეს შეტყობინება. ზოლში ჩანს, როდის მოითხოვეთ.')
    r.point(pg.locator('.o-mail-Message', has_text='დაწყების მოთხოვნა გაიგზავნა').first, 1.5)
    r.cap('მიმოწერაში ჩაიწერა, ვის გაეგზავნა. ღილაკი არის ნაბიჯის ბარათზეც „ჩემს დავალებებში“ - მას ხედავს მხოლოდ ამ ნაბიჯის შემსრულებელი.')
    r.cap('იგივე ღილაკი მუშაობს მაშინაც, როცა წინა დავალება შეჩერებული არ არის და უბრალოდ გვიანდება.')


# ---------------------------------------------------------------- 4: the one who holds lets the next start
def nino_allows(r, t):
    pg = r.pg
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.mark_start()
    r.cap('შეჩერებული დავალების შემსრულებელმა მიიღო მოთხოვნა. მის ბარათზე არის ზოლი: „შემდეგი დავალება ელოდება“.')
    r.point(card(r, S3).locator('.o_sh_held_strip'), 1.8)
    r.cap('ღილაკი „▶ შემდეგის დაშვება“ ბარათზეც არის და დავალების შიგნითაც. გავხსნათ დავალება.')
    r.click(card(r, S3).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.point(pg.locator('.o-mail-Message', has_text='ითხოვს შემდეგი დავალების დაწყებას').first, 1.8)
    r.cap('მიმოწერაში ჩანს მოთხოვნა: ვინ ითხოვს დაწყებას, რომელი დავალებისთვის და რა შეგიძლიათ გააკეთოთ.')
    r.point(pg.locator('.o_form_view .alert-info:visible', has_text='შემდეგი დავალება ელოდება').first, 1.8)
    r.cap('ჩანს, რომელი დავალება ელოდება. დაშვება სავალდებულო არ არის - დაუშვით მხოლოდ მაშინ, თუ შემდეგი საქმე თქვენ გარეშეც შეიძლება დაიწყოს.')
    r.click(pg.locator('button[name="action_sh_allow_next"]:visible'), 1.0, 1.5)
    pg.wait_for_selector('.modal:visible')
    r.cap('სისტემა დასტურს გთხოვთ: შემდეგი დავალება დაიწყება ამ შეჩერებული დავალების გარეშე.')
    r.click(pg.locator('.modal:visible footer .btn-primary, .modal:visible .modal-footer .btn-primary'), 1.0, 2.5)
    for _n in range(30):
        if rpc(MANAGER, 'project.task', 'read', [[t['s4']]], {'fields': ['sh_continue_ok']})[0]['sh_continue_ok']:
            break
        r.wait(0.5)
    else:
        raise RuntimeError('the next step did not get the permission')
    r.read(1.5)
    r.cap('ნებართვა გაცემულია. თქვენი დავალება ისევ შეჩერებულია - გააგრძელებთ, როცა დაბრკოლება მოიხსნება.')


# ---------------------------------------------------------------- 5: the next one starts
def luka_starts(r, t):
    pg = r.pg
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.mark_start()
    r.point(card(r, S4).locator('.o_sh_step_badge'), 1.8)
    r.cap('შემდეგი ნაბიჯის შემსრულებელმა მიიღო შეტყობინება. ბარათზე ახლა წერია „შენი ჯერია“.')
    r.click(card(r, S4).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.point(pg.locator('.o-mail-Message', has_text='დართო ნება').first, 1.5)
    r.cap('მიმოწერაში ჩანს, ვინ და როდის დართო ნება. გამოჩნდა ღილაკი „მიღება“ - დავალება შეიძლება დაიწყოს.')
    r.click(pg.locator('button[name="action_sh_accept"]:visible'), 1.0, 1.5)
    s.until(t['s4'], ('accepted',), r)
    r.read(1.5)
    r.title('მოკლედ', '1. დაფაზე ჩანს მთავარი დავალება; ნაბიჯები - ბარათის ღილაკით „თანმიმდევრობა“\n'
                      '2. თქვენი ნაბიჯები სიაში მუქი ლურჯი შრიფტითაა\n3. ნაბიჯი იწყება, როცა წინა დადასტურდება; ერთ ნაბიჯში მდგომი დავალებები ერთდროულად სრულდება\n'
                      '4. რიგი იცვლება ბარათის გადათრევით, ჩანართში „თანმიმდევრობა“\n5. ელოდებით? „დაწყების მოთხოვნა“. შეჩერებული წინა დავალების შემსრულებელი უშვებს: „შემდეგის დაშვება“', 0.5)
    r.read(11)


def record(t):
    photo = demo_photo()
    parts = [sit('v4a', MANAGER, s.ROLE_AUTHOR, author, t)]
    tidy(t)
    parts.append(sit('v4b', EMPLOYEE, ('თანამშრომელი - ნინო', '#2563eb'), nino_work, t, photo))
    parts.append(sit('v4c', EMPLOYEE2, ('თანამშრომელი - ლუკა', '#0891b2'), luka_waits, t))
    parts.append(sit('v4d', EMPLOYEE, ('თანამშრომელი - ნინო', '#2563eb'), nino_allows, t))
    parts.append(sit('v4e', EMPLOYEE2, ('თანამშრომელი - ლუკა', '#0891b2'), luka_starts, t))
    return parts


if __name__ == '__main__':
    ids = prepare()
    join(record(ids), '4 - თანმიმდევრობა და პარალელური დავალებები.mp4')
