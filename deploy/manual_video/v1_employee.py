# -*- coding: utf-8 -*-
"""Video manual 1 - the employee: where my tasks are, accepting, starting, a note and a file,
"შესრულებულია", a task that came back, putting a task on hold.
    run.ps1 v1_employee.py          (SH_VM_FAST=1 for a trial run without video)"""
import os
import scenes as s
from rec import Rec, rpc, join, WORK, MANAGER, EMPLOYEE

T_MAIN = 'ნოემბრის გაყიდვების ანგარიშის მომზადება'
T_BACK = 'კლიენტების სიის განახლება'
T_HOLD = 'საწყობის ნაშთების შედარება'
REASON = 'დაამატეთ კლიენტების საკონტაქტო ტელეფონები.'


def prepare():
    s.wipe()
    done = s.task('ოქტომბრის ანგარიშის ჩაბარება', days=-1)
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[done]])
    rpc(EMPLOYEE, 'project.task', 'action_sh_mark_done', [[done]])
    rpc(MANAGER, 'project.task', 'sh_approval_approve', [[done]])
    back = s.task(T_BACK, days=1, priority='1',
                  description='<p>განაახლეთ აქტიური კლიენტების სია: დასახელება, საიდენტიფიკაციო კოდი, საკონტაქტო პირი.</p>')
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[back]])
    rpc(EMPLOYEE, 'project.task', 'action_sh_mark_done', [[back]])
    rpc(MANAGER, 'project.task', 'sh_approval_reject', [[back], REASON])
    hold = s.task(T_HOLD, days=4, priority='1',
                  description='<p>შეადარეთ საწყობის ფაქტობრივი ნაშთები პროგრამის მონაცემებს და ჩამოწერეთ სხვაობები.</p>')
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[hold]])
    s.move(EMPLOYEE, hold, 'in_progress')
    s.task('მომწოდებელთან ხელშეკრულების გადახედვა', days=6)
    main = s.task(T_MAIN, days=2, priority='2', description=(
        '<p>მოამზადეთ ნოემბრის გაყიდვების ანგარიში:</p><ul><li>გაყიდვები პროდუქტების მიხედვით</li>'
        '<li>შედარება ოქტომბერთან</li><li>სამი ყველაზე მსხვილი კლიენტი</li></ul><p>ანგარიში ატვირთეთ ფაილად.</p>'))
    return {'main': main, 'back': back, 'hold': hold}


def demo_file():
    """A small PDF to attach - the "report" of the story."""
    path = os.path.join(WORK, 'გაყიდვების ანგარიში - ნოემბერი.pdf')
    r = Rec('pdf', video=False)
    r.pg.set_content('<html><body style="font-family:Sylfaen,Segoe UI;padding:60px"><h1>გაყიდვების ანგარიში - ნოემბერი</h1>'
                     '<p>სადემონსტრაციო ფაილი ვიდეო სახელმძღვანელოსთვის.</p></body></html>')
    r.pg.pdf(path=path)
    r.close()
    return path


def card(r, name):
    return r.pg.locator('.o_kanban_record', has_text=name)


def record(t):
    pdf = demo_file()
    r = s.sitting('v1', EMPLOYEE, s.ROLE_EMPLOYEE)
    try:
        return play(r, t, pdf)
    except Exception:
        print('FAILED at', r.pg.url, '| screenshot:', r.shot('FAILED'))
        r.close()
        raise


def play(r, t, pdf):
    pg = r.pg
    s.warm(r, t['hold'], ('შეჩერებული',))
    r.goto('/odoo', '.o-app-menu-item', 1.5)
    r.title('დავალებების მართვა', 'სახელმძღვანელო თანამშრომლისთვის\n\nროგორ ვნახო, მივიღო და შევასრულო დავალება', 0.5)
    r.mark_start()
    r.read(5)
    r.untitle()

    # 1 - where the tasks are
    r.cap('სისტემაში შესვლის შემდეგ ხედავთ აპლიკაციებს. დავალებები არის აპლიკაციაში „პროექტი“.')
    r.click(pg.locator('a.o-app-menu-item', has_text='პროექტი'), 1.0, 2.5)
    pg.wait_for_selector('.o_action_manager .o_action, .o_action_manager .o_view_controller')
    r.click(pg.locator('.o_menu_sections a, .o_menu_sections button', has_text='მთავარი'), 0.8, 3.0)
    r.cap('„მთავარი“ - თქვენი პირადი გვერდი: რამდენი დავალება გაქვთ ღია, რამდენი მიმდინარეობს და რამდენია ვადაგადაცილებული.')
    box = pg.locator('.o_action_manager').get_by_text('ჩემი დავალებები კალენდარზე').first
    r.point(box, 1.0)
    r.cap('ქვემოთ - თქვენი დავალებები კალენდარზე, ვადების მიხედვით. დავალებაზე დაჭერით ის იხსნება.')

    # 2 - my tasks
    r.click(pg.locator('.o_menu_sections a, .o_menu_sections button', has_text='დავალებები'), 0.8, 1.0)
    r.click(pg.locator('.dropdown-item:visible', has_text='ჩემი დავალებები'), 0.8, 3.0)
    pg.wait_for_selector('.o_kanban_view')
    r.cap('„ჩემი დავალებები“ - ყველა დავალება, სადაც თქვენ ხართ შემსრულებელი. სვეტები პირადია: დღეს, ეს კვირა, ეს თვე.')
    r.point(card(r, T_MAIN), 1.5)
    r.cap('ბარათზე ჩანს დავალების სათაური, დეპარტამენტი, ვადა და პრიორიტეტი. ქვედა ზოლი აჩვენებს, რა სტადიაზეა დავალება.')
    r.click(card(r, T_MAIN).locator('.o_sh_card_title, .o_sh_card_top').first, 0.8, 3.0)
    pg.wait_for_selector('.o_form_view')

    # 3 - reading the task
    r.cap('დავალების გვერდი. ზემოთ - სტადიები: ახალი → მიღებული → მიმდინარე → შემოწმებაზე.')
    r.point(pg.locator('.o_form_view .o_statusbar_status'), 1.5)
    r.point(pg.locator('.o_form_view div[name="sh_responsible_id"]'), 1.0)
    r.cap('„ვინ“ - მთავარი პასუხისმგებელი, შემსრულებლები და შემმოწმებელი (ვინც დავალება მოგცათ და შედეგს შეამოწმებს).')
    r.point(pg.locator('.o_form_view div[name="date_deadline"]'), 1.2)
    r.cap('„დასრულების თარიღი“ - ვადა, რომლამდეც დავალება უნდა შესრულდეს.')
    desc = pg.locator('.o_form_view div[name="description"]')
    r.point(desc, 1.5)
    r.cap('„აღწერილობაში“ წერია, კონკრეტულად რა არის გასაკეთებელი.')

    # 4 - accept, start
    s.form_top(r)
    r.cap('დავალების გაცნობის შემდეგ დააჭირეთ „მიღება“ - ავტორი დაინახავს, რომ დავალება მიიღეთ.')
    r.click(pg.locator('button[name="action_sh_accept"]:visible'), 1.0, 1.5)
    s.until(t['main'], ('accepted',), r)
    r.read(1.5)
    r.cap('სტადია გახდა „მიღებული“. როცა მუშაობას დაიწყებთ, სტადიების ზოლზე დააჭირეთ „მიმდინარე“.')
    s.pick_stage(r, 'მიმდინარე', 1.5)
    s.until(t['main'], ('in_progress',), r)
    r.read(1.5)

    # 5 - note and file
    r.cap('მარჯვნივ არის დავალების ისტორია და მიმოწერა. შენიშვნის დასაწერად დააჭირეთ „შიდა შენიშვნა“.')
    r.click(pg.locator('.o-mail-Chatter button', has_text='შიდა შენიშვნა'), 0.8, 1.2)
    r.type(pg.locator('textarea.o-mail-Composer-input'), 'ანგარიში მზადაა, ფაილი თან ერთვის.')
    with pg.expect_file_chooser() as fc:
        r.click(pg.locator('.o-mail-Composer button[name="upload-files"]'), 0.8, 0.5)
    fc.value.set_files(pdf)
    r.wait(2.5)
    r.cap('ქაღალდის სამაგრით ამაგრებთ ფაილს - ანგარიშს, ფოტოს ან სხვა დოკუმენტს.')
    r.click(pg.locator('button.o-mail-Composer-send'), 0.8, 2.5)
    r.cap('შენიშვნა და ფაილი დავალებაზე შეინახა - მათ ხედავს ყველა, ვინც ამ დავალებაში მონაწილეობს.')
    r.point(pg.locator('.o_form_view .o_widget_sh_task_chat_button, .o_form_view button:has-text("საერთო ჩატი")'), 1.2)
    r.cap('„საერთო ჩატი“ - დავალების მონაწილეების საერთო მიმოწერა, თუ რამე გაქვთ შესათანხმებელი.')

    # 6 - done
    r.cap('სამუშაოს დასრულების შემდეგ დააჭირეთ „შესრულებულია“.')
    r.click(pg.locator('button[name="action_sh_mark_done"]:visible'), 1.0, 1.5)
    pg.wait_for_selector('.modal:visible')
    r.cap('სისტემა გეკითხებათ დასტურს: დავალება გადავა შემოწმებაზე.')
    r.click(pg.locator('.modal button:visible', has_text='კი, შესრულდა'), 1.0, 1.5)
    s.until(t['main'], ('review',), r)
    r.read(1.5)
    r.cap('დავალება „შემოწმებაზეა“. შემმოწმებელს მიუვიდა შეტყობინება - ის ან დაადასტურებს, ან დაგიბრუნებთ შესასწორებლად.')

    # 7 - a task that came back
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.cap('თუ შემმოწმებელმა დავალება დააბრუნა, მიიღებთ შეტყობინებას, ბარათზე კი გამოჩნდება „დაბრუნებული“.')
    r.click(card(r, T_BACK).locator('.o_sh_card_title, .o_sh_card_top').first, 1.2, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.point(pg.locator('.o_form_view .alert:visible').first, 1.5)
    r.cap('დავალების თავში, ფერად ზოლში, წერია დაბრუნების მიზეზი - რა არის გასასწორებელი.')
    r.cap('გაასწორეთ, რაც მოგთხოვეს, და ისევ დააჭირეთ „შესრულებულია“.')
    r.click(pg.locator('button[name="action_sh_mark_done"]:visible'), 1.0, 1.5)
    r.click(pg.locator('.modal button:visible', has_text='კი, შესრულდა'), 0.8, 1.5)
    s.until(t['back'], ('review',), r)
    r.read(1.5)

    # 8 - hold
    s.open_task(r, t['hold'])
    r.cap('თუ დავალებას ვერ აგრძელებთ (მაგალითად, ელოდებით ინფორმაციას), გადაიყვანეთ „შეჩერებულზე“.')
    s.pick_stage(r, 'შეჩერებული', 2.0, modal=True)
    pg.wait_for_selector('.modal:visible')
    r.cap('შეჩერებისას მიზეზის მითითება სავალდებულოა.')
    r.type(pg.locator('.modal textarea:visible'), 'ველოდები საწყობის ინვენტარიზაციის აქტს.')
    r.point(pg.locator('.modal div[name="resume_date"]'), 1.0)
    r.cap('შეგიძლიათ მიუთითოთ, როდის გაგრძელდება მუშაობა.')
    r.click(pg.locator('.modal button[name="action_confirm"]:visible'), 1.0, 2.0)
    s.until(t['hold'], ('on_hold',), r)
    r.read(1.5)
    r.cap('დავალება შეჩერდა, მიზეზი ჩანს დავალების თავში. შემმოწმებელმა ეს იცის.')
    r.cap('გასაგრძელებლად სტადიების ზოლზე აირჩიეთ სამუშაო სტადია - დავალება „ახალში“ დაბრუნდება და თავიდან მიიღებთ.')

    # 9 - the end
    r.goto('/odoo/my-tasks', '.o_kanban_record', 2.0)
    r.cap('ასე ჩანს თქვენი დავალებები ახლა. დასრულებულს შემმოწმებლის დადასტურების შემდეგ ნახავთ სვეტში „დასრულებულია“.')
    r.title('მოკლედ', '1. „პროექტი“ → „დავალებები“ → „ჩემი დავალებები“\n2. გახსენით დავალება და დააჭირეთ „მიღება“\n'
                      '3. მუშაობის დაწყებისას - „მიმდინარე“\n4. დასრულებისას - „შესრულებულია“\n5. თუ დაგიბრუნდათ - გაასწორეთ და ისევ „შესრულებულია“', 0.5)
    r.read(9)
    return [r.close()]


if __name__ == '__main__':
    ids = prepare()
    join(record(ids), '1 - თანამშრომელი.mp4')
