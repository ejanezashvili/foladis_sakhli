# -*- coding: utf-8 -*-
"""The scenes of video manual 3 (the head / reviewer) - started by v3_reviewer.py."""
import scenes as s
from rec import MANAGER
from v3_reviewer import T_OK, T_NO, T_FORM, T_HOLD, T_LATE


def record(t):
    r = s.sitting('v3', MANAGER, s.ROLE_REVIEWER)
    try:
        return play(r, t)
    except Exception:
        print('FAILED at', r.pg.url, '| screenshot:', r.shot('FAILED'))
        r.close()
        raise


def card(r, name):
    return r.pg.locator('.o_kanban_record', has_text=name)


def play(r, t):
    pg = r.pg
    s.warm(r, t['late'], ('გაუქმებული',))
    r.goto('/odoo', '.o-app-menu-item', 1.5)
    r.title('დავალებების მართვა', 'სახელმძღვანელო ხელმძღვანელისთვის და შემმოწმებლისთვის\n\nროგორ შევამოწმო, დავადასტურო ან დავაბრუნო დავალება', 0.5)
    r.mark_start()
    r.read(5.5)
    r.untitle()

    # 1 - the approvals app
    r.cap('დავალების შემმოწმებელი არის ის, ვინც დავალება შექმნა. როცა შემსრულებელი დააჭერს „შესრულებულია“, დავალება თქვენთან მოდის.')
    r.cap('ყველა ასეთი დავალება ერთ ადგილას გროვდება - აპლიკაციაში „დადასტურებები“.')
    r.click(pg.locator('a.o-app-menu-item', has_text='დადასტურებები'), 1.0, 3.0)
    pg.wait_for_selector('.o_sh_ap_card')
    r.point(pg.locator('.o_sh_ap_tabs'), 1.2)
    r.cap('„ჩემი დასადასტურებელი“ - რაც თქვენს გადაწყვეტილებას ელოდება. „ჩემი გაგზავნილი“ - რაც თქვენ გაგზავნეთ შემოწმებაზე.')
    r.point(pg.locator('.o_sh_ap_stats'), 1.2)
    r.cap('ზემოთ ჩანს: სულ რამდენი ელოდება, რამდენი ელოდება 2 დღეზე მეტია და რამდენს გაუვიდა ვადა.')
    row = pg.locator('.o_sh_ap_card', has_text=T_OK)
    r.point(row, 1.2)
    r.cap('თითო სტრიქონი - ერთი დავალება: ვინ შეასრულა, რომელი დეპარტამენტია და როდისაა ვადა.')

    # 2 - look and confirm
    r.cap('დეტალების სანახავად დააჭირეთ დავალების სათაურს.')
    r.click(row.locator('.o_sh_ap_title'), 0.8, 2.5)
    pg.wait_for_selector('.o_sh_ap_cols')
    r.point(pg.locator('.o_sh_ap_left .o_sh_ap_panel').nth(0), 1.3)
    r.cap('მარცხნივ: რა იყო დავალება, მიმაგრებული ფაილები და დავალების გზა - ვინ როდის რა გააკეთა.')
    r.point(pg.locator('.o_sh_ap_facts'), 1.3)
    r.cap('მარჯვნივ - მოკლე მონაცემები: შემსრულებელი, ვადა, რამდენი დრო დაიხარჯა.')
    r.cap('თუ სამუშაო სწორადაა შესრულებული, დააჭირეთ „დადასტურება“.')
    r.click(pg.locator('.o_sh_ap_right button.o_sh_ap_ok'), 1.0, 1.5)
    pg.wait_for_selector('.o_sh_ap_dlg')
    r.cap('სისტემა დასტურს გთხოვთ.')
    r.click(pg.locator('.o_sh_ap_dlg button', has_text='კი, დადასტურდეს'), 1.0, 2.0)
    s.until(t['ok'], ('done',), r)
    r.read(1.5)
    r.cap('დავალება გადავიდა „დასრულებულში“ და სიიდან გაქრა. გაიხსნა შემდეგი დასადასტურებელი.')

    # 3 - reject with a reason
    back = pg.locator('.o_sh_ap_back')
    if back.count():
        r.click(back, 0.8, 2.0)
    else:
        r.goto('/odoo/sh-approvals', '.o_sh_ap_card', 2.0)
    pg.wait_for_selector('.o_sh_ap_card')
    row = pg.locator('.o_sh_ap_card', has_text=T_NO)
    r.cap('თუ სამუშაო გასასწორებელია, დააჭირეთ „უარყოფა“ - პირდაპირ სიიდანაც შეიძლება.')
    r.click(row.locator('.o_sh_ap_no'), 1.0, 1.5)
    pg.wait_for_selector('.o_sh_ap_dlg')
    r.cap('მიზეზის მითითება სავალდებულოა - დაწერეთ, კონკრეტულად რა არის გასასწორებელი.')
    r.type(pg.locator('.o_sh_ap_dlg textarea'), 'სიას აკლია კლიენტების საკონტაქტო ტელეფონები - გთხოვთ დაამატოთ.')
    r.click(pg.locator('.o_sh_ap_dlg button.o_sh_ap_rej'), 1.0, 2.0)
    s.until(t['no'], ('returned',), r)
    r.read(1.5)
    r.cap('დავალება დაუბრუნდა შემსრულებელს. ის მიიღებს შეტყობინებას და მიზეზს დავალებაზე დაინახავს.')
    r.click(pg.locator('.o_sh_ap_tab', has_text='ისტორია'), 0.8, 2.5)
    r.cap('„ისტორიაში“ ჩანს თქვენი ყველა გადაწყვეტილება - რა დაადასტურეთ და რა დააბრუნეთ.')

    # 4 - the department board
    r.goto('/odoo/project', '.o_kanban_record', 2.0)
    r.cap('აპლიკაცია „პროექტი“ - დეპარტამენტები, რომლებსაც ხედავთ. დეპარტამენტზე დაჭერით იხსნება მისი დაფა.')
    r.click(pg.locator('.o_kanban_record', has_text=s.DEPT), 1.0, 3.5)
    pg.wait_for_selector('.o_kanban_group')
    r.cap('დაფაზე ოთხი სვეტია: ახალი, მუშავდება, შემოწმებაზე და დასრულებული. ასე ჩანს, რა ეტაპზეა თითოეული დავალება.')
    r.point(card(r, T_LATE), 1.5)
    r.cap('ვადაგადაცილებული დავალება წითლადაა მონიშნული.')
    r.point(card(r, T_NO), 1.3)
    r.cap('„მუშავდება“ სვეტში ბარათზე ჩანს ზუსტი მდგომარეობა: მიღებული, მიმდინარე, შეჩერებული ან დაბრუნებული.')

    # 5 - confirm from the task, with the final note
    r.cap('დავალების დადასტურება თვითონ დავალებიდანაც შეიძლება. გავხსნათ „შემოწმებაზე“ მყოფი დავალება.')
    r.click(card(r, T_FORM).locator('.o_sh_card_title, .o_sh_card_top').first, 1.0, 3.0)
    pg.wait_for_selector('.o_form_view')
    r.point(pg.locator('.o-mail-Chatter'), 1.3)
    r.cap('მარჯვნივ ჩანს დავალების მთელი ისტორია და შემსრულებლის შენიშვნები.')
    r.cap('დასადასტურებლად დააჭირეთ „შემოწმებულია“.')
    r.click(pg.locator('button[name="action_sh_review_ok"]:visible'), 1.0, 1.5)
    pg.wait_for_selector('.modal:visible')
    r.click(pg.locator('.modal button:visible', has_text='კი, დადასტურდეს'), 1.0, 2.0)
    pg.wait_for_selector('.modal button[name="action_confirm"]:visible')
    r.cap('იხსნება „საბოლოო პროექტი“ - აქ შეგიძლიათ დაწეროთ შედეგის მოკლე აღწერა და მიამაგროთ ფოტო ან ფაილი.')
    note = pg.locator('.modal div[name="note"] textarea:visible, .modal div[name="note"] .odoo-editor-editable:visible, .modal textarea:visible')
    r.type(note, 'შეთავაზება გაგზავნილია კლიენტთან.', clear=False)
    r.click(pg.locator('.modal button[name="action_confirm"]:visible'), 1.0, 2.0)
    s.until(t['form'], ('done',), r)
    r.read(1.5)
    r.cap('დავალება დასრულდა. ჩანაწერი ვინ და როდის დაასრულა, ინახება ჩანართში „საბოლოო პროექტი“.')

    # 6 - a task on hold
    s.open_task(r, t['hold'])
    r.point(pg.locator('.o_form_view .alert:visible').first, 1.5)
    r.cap('შეჩერებულ დავალებაზე ჩანს მიზეზი. როცა დაბრკოლება მოიხსნება, დავალება შეგიძლიათ განაახლოთ.')
    s.pick_stage(r, 'მიმდინარე', 2.0)
    s.until(t['hold'], ('new',), r)
    r.read(1.5)
    r.cap('განახლებული დავალება ყოველთვის „ახალში“ ბრუნდება - შემსრულებელი იღებს შეტყობინებას და თავიდან იღებს დავალებას.')

    # 7 - cancel
    s.open_task(r, t['late'])
    r.cap('თუ დავალება აღარ არის საჭირო, გააუქმეთ: სტადიების ზოლზე დააჭირეთ „...“ და აირჩიეთ „გაუქმებული“.')
    s.pick_stage(r, 'გაუქმებული', 2.0, modal=True)
    pg.wait_for_selector('.modal:visible')
    r.type(pg.locator('.modal textarea:visible'), 'დოკუმენტაცია აღარ არის საჭირო.')
    r.cap('გაუქმებისასაც მიზეზი სავალდებულოა. გაუქმება და დაბრუნება შეუძლია მხოლოდ შემმოწმებელს.')
    r.click(pg.locator('.modal button[name="action_confirm"]:visible'), 1.0, 2.0)
    s.until(t['late'], ('cancelled',), r)
    r.read(1.5)

    # 8 - the reports
    r.goto('/odoo/sh-timeline', '.o_action', 3.5)
    allb = pg.locator('.o_action button:visible', has_text='ყველა')
    if allb.count():
        r.click(allb, 0.8, 3.0)
    r.cap('აპლიკაცია „რეპორტინგი“ → „Timeline და დატვირთვა“: ვინ რაზე მუშაობს და ვისი დავალებების ვადა როდის იწურება.')
    r.goto('/odoo/sh-deadlines', '.o_action', 3.5)
    r.cap('„ვადების დაცვა“ - რამდენი დავალება დასრულდა დროულად და რამდენი დაგვიანებით. მონაცემები იტვირთება Excel-ად და PDF-ად.')

    r.title('მოკლედ', '1. დასადასტურებელი დავალებები - აპლიკაციაში „დადასტურებები“\n2. სწორია - „დადასტურება“; გასასწორებელია - „უარყოფა“ მიზეზით\n'
                      '3. დეპარტამენტის დაფა აჩვენებს, რა ეტაპზეა ყველა დავალება\n4. შეჩერება, განახლება, გაუქმება - სტადიების ზოლიდან, მიზეზით\n5. შედეგები - აპლიკაციაში „რეპორტინგი“', 0.5)
    r.read(10)
    return [r.close()]
