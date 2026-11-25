# -*- coding: utf-8 -*-
"""Video manual 2 - creating a task: from the department board, who / when, the description,
"დამატებით ხედავენ", a sequence of steps, a repeating task, saving as a template.
    run.ps1 v2_create.py [-Fast]"""
import datetime
import scenes as s
from rec import Rec, rpc, join, FAST, MANAGER, EMPLOYEE, EMPLOYEE2

T_NEW = 'ფასების შეთავაზების მომზადება კლიენტისთვის'
STEP1 = 'ფასების გაანგარიშება'
STEP2 = 'შეთავაზების გაფორმება და გაგზავნა'
TEMPLATE = 'ფასების შეთავაზება'
DEMO_NAME = 'ნიმუშაძე'      # typed into the people fields: only the demo users match


def prepare():
    s.wipe()
    a = s.task('ნოემბრის გაყიდვების ანგარიშის მომზადება', days=2, priority='2')
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[a]])
    s.move(EMPLOYEE, a, 'in_progress')
    s.task('მომწოდებელთან ხელშეკრულების გადახედვა', assignee=EMPLOYEE2, days=6)
    return {}


def day(days):
    return datetime.date.today() + datetime.timedelta(days=days)


def new_id():
    ids = rpc(MANAGER, 'project.task', 'search', [[('name', '=', T_NEW), ('is_template', '=', False)]])
    return ids and ids[0]


def record(t):
    r = s.sitting('v2', MANAGER, s.ROLE_AUTHOR)
    try:
        return play(r, t)
    except Exception:
        print('FAILED at', r.pg.url, '| screenshot:', r.shot('FAILED'))
        r.close()
        raise


def _pick(r, inp, text, items, pick):
    """Types the name and picks it from the list; typed again when the list hangs on loading
    (the line to the server drops for a moment now and then)."""
    for attempt in range(4):
        r.type(inp, text, clear=True)
        item = items.filter(has_text=pick)
        try:
            item.first.wait_for(state='visible', timeout=7000)
        except Exception:
            print('  the list did not load, typing again')
            inp.first.fill('')
            r.pg.keyboard.press('Escape')
            r.wait(2.0)
            continue
        r.click(item, 0.7, 1.0)
        return
    raise RuntimeError('no list for %s' % pick)


def many2x(r, field, text, pick, scope='.o_form_view'):
    """A person field of the form."""
    pg = r.pg
    _pick(r, pg.locator('%s div[name="%s"] input' % (scope, field)), text,
          pg.locator('.o-autocomplete--dropdown-menu .dropdown-item:visible, .o-autocomplete--dropdown-item:visible'), pick)


def picker(r, box, text, pick):
    """The same in the step window (its own people picker)."""
    _pick(r, box.locator('input.o_sh_user_input'), text, r.pg.locator('.o_sh_user_menu .dropdown-item:visible'), pick)


def add_step(r, name, who, days):
    pg = r.pg
    pop = pg.locator('.o_sh_chain_pop')
    pop.wait_for(state='visible', timeout=15000)
    r.type(pop.locator('input[placeholder^="რა უნდა გაკეთდეს"]'), name)
    sel = pop.locator('select[title="დეპარტამენტი"]')
    value = sel.evaluate("(e, name) => { const o = [...e.options].find(o => o.textContent.includes(name)); return o ? o.value : ''; }", s.DEPT)
    if sel.input_value() != value:
        r.point(sel, 0.6)
        sel.select_option(value)
        r.wait(0.8)
    picker(r, pop.locator('div[title="პასუხისმგებელი"]'), DEMO_NAME, who)
    date = pop.locator('input[type="date"][title="ვადა"]').first
    r.point(date, 0.6)
    date.fill(day(days).isoformat())
    date.dispatch_event('change')
    r.wait(0.8)


def save(r):
    b = r.pg.locator('.o_form_button_save:visible')
    if b.count():
        r.click(b, 1.0, 2.5)


def play(r, t):
    pg = r.pg
    r.goto('/odoo/project', '.o_kanban_record', 1.5)
    r.title('დავალების შექმნა', 'როგორ შევქმნა დავალება, მივუთითო შემსრულებელი და ვადა,\nდავყო ნაბიჯებად და შევინახო შაბლონად', 0.5)
    r.mark_start()
    r.read(5.5)
    r.untitle()

    # 1 - the board, the new task
    r.cap('დავალება იქმნება დეპარტამენტის დაფიდან: აპლიკაცია „პროექტი“ → თქვენი დეპარტამენტი.')
    r.click(pg.locator('.o_kanban_record', has_text=s.DEPT), 1.0, 3.5)
    pg.wait_for_selector('.o_kanban_group')
    r.cap('ეს არის დეპარტამენტის დაფა. ახალი დავალებისთვის დააჭირეთ „ახალი“.')
    r.click(pg.locator('.o_control_panel button.o-kanban-button-new, .o_control_panel button:has-text("ახალი")'), 1.0, 2.0)
    quick = pg.locator('.o_kanban_quick_create')
    quick.wait_for(state='visible', timeout=15000)
    r.type(quick.locator('input').first, T_NEW)
    r.cap('ჩაწერეთ სათაური - მოკლედ და გასაგებად, რა უნდა გაკეთდეს. დეტალებისთვის დააჭირეთ „შეცვლა“.')
    r.click(quick.locator('button.o_kanban_edit, button:has-text("შეცვლა")'), 1.0, 3.5)
    pg.wait_for_selector('.o_form_view')
    r.wait(1.5)

    # 2 - who
    r.point(pg.locator('.o_form_view div[name="sh_department_project_ids"]'), 1.2)
    r.cap('„დეპარტამენტი“ უკვე შევსებულია. თუ დავალება რამდენიმე დეპარტამენტს ეხება, დაამატეთ ისინიც.')
    r.cap('„მთავარი პასუხისმგებელი“ - ვინ აგებს პასუხს შედეგზე. დაიწყეთ სახელის წერა და აირჩიეთ სიიდან.')
    many2x(r, 'sh_responsible_id', DEMO_NAME, 'ნინო')
    r.cap('„შემსრულებლები“ - ვინ ასრულებს დავალებას. შეიძლება რამდენიმე ადამიანი იყოს.')
    if not pg.locator('.o_form_view div[name="user_ids"] .o_tag, .o_form_view div[name="user_ids"] .o_avatar').count():
        many2x(r, 'user_ids', DEMO_NAME, 'ნინო')
    else:
        r.point(pg.locator('.o_form_view div[name="user_ids"]'), 1.2)
    r.point(pg.locator('.o_form_view div[name="reviewer_ids"]'), 1.2)
    r.cap('„შემმოწმებელი“ ავტომატურად თქვენ ხართ - ვინც დავალება შექმნა, ის ამოწმებს და ადასტურებს შედეგს.')

    # 3 - when, priority, description
    r.cap('„დასრულების თარიღი“ - ვადა. დააჭირეთ ველს და აირჩიეთ თარიღი კალენდარში.')
    dl = pg.locator('.o_form_view div[name="date_deadline"] input').first
    r.point(dl, 0.6)
    dl.click()
    r.read(1.5)
    dl.fill(day(3).strftime('%d.%m.%Y') + ' 18:00:00')
    dl.press('Enter')
    r.wait(0.8)
    pg.keyboard.press('Escape')
    r.wait(0.8)
    r.click(pg.locator('.o_form_view div[name="priority"] input'), 0.8, 1.0)
    r.click(pg.locator('.o_select_menu_menu .o_select_menu_item:visible, .o-dropdown--menu .dropdown-item:visible', has_text='მაღალი'), 0.7, 1.0)
    r.cap('„პრიორიტეტი“: დაბალი, საშუალო, მაღალი ან კრიტიკული.')
    desc = pg.locator('.o_form_view div[name="description"] .odoo-editor-editable')
    r.point(desc, 0.6)
    desc.click()
    pg.keyboard.type('მოამზადეთ ფასების შეთავაზება: პროფილები, ბადეები, მიწოდების ვადა და გადახდის პირობები.', delay=5 if FAST else 40)
    r.wait(0.8)
    r.cap('„აღწერილობაში“ დაწერეთ დეტალურად, რა არის გასაკეთებელი და რა შედეგს ელით.')
    s.form_top(r)
    save(r)
    r.cap('ცვლილებები ინახება ღილაკით „შენახვა“ (ან თავისით, გვერდიდან გასვლისას). შემსრულებელს მიუვა შეტყობინება.')

    # 4 - extra viewers
    r.cap('„დამატებით ხედავენ“ - ადამიანები, რომლებიც დავალებაში არ მონაწილეობენ, მაგრამ უნდა ხედავდნენ მას.')
    many2x(r, 'sh_extra_viewer_ids', DEMO_NAME, 'ლუკა')
    save(r)
    r.cap('ჩვეულებრივ დავალებას ხედავენ მხოლოდ მისი მონაწილეები: შემსრულებელი, პასუხისმგებელი და შემმოწმებელი.')

    # 5 - the sequence
    r.cap('დიდი დავალება შეგიძლიათ ნაბიჯებად დაყოთ - ჩანართში „თანმიმდევრობა“.')
    tab = pg.locator('.o_form_view .nav-tabs .nav-link', has_text='თანმიმდევრობა')
    r.click(tab, 1.0, 2.0)
    r.click(pg.locator('.o_sh_chain_addbtn'), 1.0, 1.5)
    r.cap('თითო ნაბიჯი ცალკე დავალებაა: თავისი სახელით, პასუხისმგებლით და ვადით.')
    add_step(r, STEP1, 'ნინო', 1)
    r.click(pg.locator('.o_sh_chain_pop button.btn-primary', has_text='დამატება'), 1.0, 3.0)
    pg.wait_for_selector('.o_sh_chain_card')
    r.cap('პირველი ნაბიჯი დაემატა. მეორე ნაბიჯის დასამატებლად დააჭირეთ ბარათის „+“-ს.')
    r.click(pg.locator('.o_sh_chain_card', has_text=STEP1).locator('.o_sh_card_plus'), 1.0, 1.5)
    add_step(r, STEP2, 'ლუკა', 3)
    r.point(pg.locator('.o_sh_chain_pop a', has_text='ქვედავალება'), 1.0)
    r.cap('ნაბიჯს შეიძლება ქვედავალებებიც დაუმატოთ, ან მონიშნოთ, რომ სხვა ნაბიჯის პარალელურად სრულდება.')
    r.click(pg.locator('.o_sh_chain_pop button.btn-primary', has_text='დამატება'), 1.0, 3.0)
    r.point(pg.locator('.o_sh_chain_canvas'), 1.5)
    r.cap('მეორე ნაბიჯი ელოდება პირველს: სანამ პირველი არ დასრულდება, მეორეს შემსრულებელი მას ვერ დაიწყებს.')
    r.cap('როცა ყველა ნაბიჯი დადასტურდება, მთავარი დავალება თავისით გადავა შემოწმებაზე.')

    # 6 - repeating
    s.form_top(r)
    rep = pg.locator('.o_form_view div[name="sh_repeat"] input')
    r.cap('თუ დავალება რეგულარულად მეორდება (მაგალითად, ყოველთვიური ანგარიში), მონიშნეთ „განმეორებადი“.')
    r.click(rep, 1.0, 1.5)
    r.point(pg.locator('.o_form_view div[name="sh_repeat_interval"], .o_form_view div[name="sh_repeat_unit"]').first, 1.2)
    r.cap('მიუთითეთ, რა სიხშირით განმეორდეს და როდემდე - სისტემა ახალ დავალებას თვითონ შექმნის.')
    r.click(rep, 0.8, 1.2)
    r.cap('ამ დავალებას განმეორება არ სჭირდება - მონიშვნას ვხსნით.')

    # 7 - template
    r.cap('ხშირად გამოსაყენებელი დავალება შეინახეთ შაბლონად - დისკეტის ნიშნით სათაურის გვერდით.')
    r.click(pg.locator('.o_form_view button[name="action_sh_save_template"]:visible'), 1.0, 2.0)
    pg.wait_for_selector('.modal:visible')
    r.type(pg.locator('.modal div[name="name"] input:visible'), TEMPLATE)
    r.click(pg.locator('.modal button[name="action_confirm"]:visible'), 1.0, 2.5)
    r.cap('შაბლონი შენახულია. შემდეგ ჯერზე დააჭირეთ „შაბლონები“ და აირჩიეთ „გამოყენება“ - დავალება მზა სახით შეიქმნება.')
    r.point(pg.locator('.o_form_view button[name="action_sh_open_templates"]:visible'), 1.5)

    # 8 - the board again
    r.goto('/odoo/project', '.o_kanban_record', 1.5)
    r.click(pg.locator('.o_kanban_record', has_text=s.DEPT), 0.8, 3.5)
    pg.wait_for_selector('.o_kanban_group')
    r.point(pg.locator('.o_kanban_record', has_text=T_NEW), 1.5)
    r.cap('ახალი დავალება დაფაზეა, სვეტში „ახალი“. ბარათზე ჩანს ნაბიჯების რაოდენობაც.')
    r.title('მოკლედ', '1. დეპარტამენტის დაფა → „ახალი“ → სათაური → „შეცვლა“\n2. შეავსეთ: პასუხისმგებელი, შემსრულებლები, ვადა, აღწერა\n'
                      '3. შემმოწმებელი ხართ თქვენ - შედეგს თქვენ ადასტურებთ\n4. დიდი დავალება დაყავით ნაბიჯებად („თანმიმდევრობა“)\n5. ხშირი დავალება შეინახეთ შაბლონად', 0.5)
    r.read(10)
    return [r.close()]


if __name__ == '__main__':
    ids = prepare()
    join(record(ids), '2 - დავალების შექმნა.mp4')
