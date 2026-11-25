# -*- coding: utf-8 -*-
"""Video manual 3 - the head / reviewer: the "დადასტურებები" app (confirm, reject with a reason),
the department board, confirming from the task with the final note, resuming a task on hold,
cancelling, the reports.
    run.ps1 v3_reviewer.py [-Fast]"""
import scenes as s
from rec import Rec, rpc, join, MANAGER, EMPLOYEE, EMPLOYEE2

T_OK = 'ნოემბრის გაყიდვების ანგარიშის მომზადება'
T_NO = 'კლიენტების სიის განახლება'
T_FORM = 'ფასების შეთავაზების მომზადება'
T_HOLD = 'საწყობის ნაშთების შედარება'
T_LATE = 'ძველი ტენდერის დოკუმენტაციის მოძიება'


def prepare():
    s.wipe()
    done = s.task('ოქტომბრის ანგარიშის ჩაბარება', days=-1)
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[done]])
    rpc(EMPLOYEE, 'project.task', 'action_sh_mark_done', [[done]])
    rpc(MANAGER, 'project.task', 'sh_approval_approve', [[done]])
    late = s.task(T_LATE, assignee=EMPLOYEE2, days=-2, priority='1',
                  description='<p>მოიძიეთ 2024 წლის ტენდერის დოკუმენტაცია არქივში.</p>')
    hold = s.task(T_HOLD, days=4, priority='1',
                  description='<p>შეადარეთ საწყობის ფაქტობრივი ნაშთები პროგრამის მონაცემებს.</p>')
    rpc(EMPLOYEE, 'project.task', 'action_sh_accept', [[hold]])
    s.move(EMPLOYEE, hold, 'in_progress')
    w = rpc(EMPLOYEE, 'steelhouse.task.flow.wizard', 'create', [{'task_id': hold, 'mode': 'on_hold', 'reason': 'ველოდები საწყობის ინვენტარიზაციის აქტს.'}])
    rpc(EMPLOYEE, 'steelhouse.task.flow.wizard', 'action_confirm', [[w]])
    s.task('მომწოდებელთან ხელშეკრულების გადახედვა', days=6)
    form = s.task(T_FORM, assignee=EMPLOYEE2, days=1, priority='2',
                  description='<p>მოამზადეთ ფასების შეთავაზება კლიენტისთვის: პროფილები, ბადეები, მიწოდების ვადა.</p>')
    no = s.task(T_NO, days=1, priority='1',
                description='<p>განაახლეთ აქტიური კლიენტების სია: დასახელება, საიდენტიფიკაციო კოდი, საკონტაქტო პირი, ტელეფონი.</p>')
    ok = s.task(T_OK, days=2, priority='2', description=(
        '<p>მოამზადეთ ნოემბრის გაყიდვების ანგარიში:</p><ul><li>გაყიდვები პროდუქტების მიხედვით</li>'
        '<li>შედარება ოქტომბერთან</li></ul>'))
    for tid, who in ((form, EMPLOYEE2), (no, EMPLOYEE), (ok, EMPLOYEE)):
        rpc(who, 'project.task', 'action_sh_accept', [[tid]])
        s.move(who, tid, 'in_progress')
        rpc(who, 'project.task', 'message_post', [[tid]], {'body': 'შესრულებულია, გთხოვთ გადახედოთ.', 'message_type': 'comment', 'subtype_xmlid': 'mail.mt_note'})
        rpc(who, 'project.task', 'action_sh_mark_done', [[tid]])
    return {'ok': ok, 'no': no, 'form': form, 'hold': hold, 'late': late}


if __name__ == '__main__':
    import sys
    ids = prepare()
    print(ids)
    if 'prepare' in sys.argv:
        sys.exit(0)
    from v3_play import record
    join(record(ids), '3 - ხელმძღვანელი და შემმოწმებელი.mp4')
