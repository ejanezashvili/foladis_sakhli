"""Data for the "მთავარი" (personal dashboard) page: everything is about the current user's tasks
(assignee or main responsible), counted in the user's time zone."""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

CLOSED = ('1_done', '1_canceled')
WEEKDAYS = ['ორშ', 'სამ', 'ოთხ', 'ხუთ', 'პარ', 'შაბ', 'კვი']


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def sh_dashboard_data(self):
        uid = self.env.uid
        today = fields.Date.context_today(self)
        day = lambda dt: fields.Datetime.context_timestamp(self, dt).date() if dt else False
        mine = self.search([('is_template', '=', False), ('project_id', '!=', False),
                            '|', ('user_ids', 'in', [uid]), ('sh_responsible_id', '=', uid)])
        done = mine.filtered(lambda t: t.state == '1_done')
        open_ = mine.filtered(lambda t: t.state not in CLOSED)
        overdue = open_.filtered('sh_is_overdue')
        done_day = {t.id: day(t.date_last_stage_update) for t in done}

        # this month vs last month
        m_start = today.replace(day=1)
        m_end = m_start + relativedelta(months=1, days=-1)
        lm_start = m_start - relativedelta(months=1)
        done_month = done.filtered(lambda t: done_day[t.id] and done_day[t.id] >= m_start)
        done_last = done.filtered(lambda t: done_day[t.id] and lm_start <= done_day[t.id] < m_start)
        planned_left = open_.filtered(lambda t: t.date_deadline and day(t.date_deadline) <= m_end)
        plan = len(done_month) + len(planned_left)
        month_pct = round(100 * len(done_month) / plan) if plan else 0
        vs_last = (round(100 * (len(done_month) - len(done_last)) / len(done_last)) if done_last
                   else (100 if done_month else 0))

        # this week, per day: tasks that came in / were finished
        w_start = today - timedelta(days=today.weekday())
        week = []
        for i in range(7):
            d = w_start + timedelta(days=i)
            week.append({
                'label': WEEKDAYS[i], 'date': d.isoformat(), 'today': d == today,
                'new': sum(1 for t in mine if day(t.create_date) == d),
                'done': sum(1 for t in done if done_day[t.id] == d),
            })

        def card(t):
            dl = day(t.date_deadline)
            return {
                'id': t.id, 'name': t.name, 'number': t.sh_number or '',
                'kind': 'late' if t.sh_is_overdue else (t.stage_id.sh_kind or 'new'),
                'stage': t.stage_id.name or '', 'progress': t.sh_progress,
                'deadline': dl and dl.isoformat() or '',
                'days_left': (dl - today).days if dl else None,
                'department': t.project_id.name or '',
                'done': t.state == '1_done',
            }

        # this week's deadlines (open ones + those already finished)
        w_end = w_start + timedelta(days=6)
        week_due = mine.filtered(lambda t: t.date_deadline and t.state != '1_canceled'
                                 and (w_start <= day(t.date_deadline) <= w_end or (t.sh_is_overdue)))
        week_due = week_due.sorted(lambda t: (t.state == '1_done', t.date_deadline))
        in_process = open_.filtered(lambda t: t.stage_id.sh_kind in ('accepted', 'in_progress', 'review', 'returned')
                                    or t.sh_is_overdue)
        in_process = in_process.sorted(lambda t: (not t.sh_is_overdue, t.date_deadline or fields.Datetime.now() + timedelta(days=3650)))

        # my projects (concrete project, else the department), most recently active first
        groups = {}
        for t in mine.filtered(lambda t: t.state != '1_canceled'):
            p = t.sh_project_id or t.project_id
            g = groups.setdefault(p.id, {'id': p.id, 'name': p.name, 'total': 0, 'done': 0, 'late': 0, 'ids': [],
                                         'last': t.write_date, 'is_dept': not t.sh_project_id})
            g['ids'].append(t.id)
            g['total'] += 1
            g['done'] += t.state == '1_done'
            g['late'] += bool(t.sh_is_overdue)
            g['last'] = max(g['last'], t.write_date)
        projects = sorted(groups.values(), key=lambda g: g['last'], reverse=True)[:6]
        for g in projects:
            g['last'] = False
            g['status'] = 'completed' if g['done'] == g['total'] else ('late' if g['late'] else 'in_progress')

        name = (self.env.user.name or '').split(' ')[0]
        weekday = ['ორშაბათი', 'სამშაბათი', 'ოთხშაბათი', 'ხუთშაბათი', 'პარასკევი', 'შაბათი', 'კვირა'][today.weekday()]
        return {
            'name': name,
            'today': today.isoformat(),
            'today_label': '%s, %s' % (weekday, today.strftime('%d.%m.%Y')),
            'done_all': len(done),
            'overdue': len(overdue),
            'open': len(open_),
            'in_progress': len(open_.filtered(lambda t: t.stage_id.sh_kind in ('in_progress', 'review', 'returned'))),
            'done_month': len(done_month),
            'month_pct': month_pct,
            'month_plan': plan,
            'vs_last': vs_last,
            'week': week,
            'week_due': [card(t) for t in week_due[:8]],
            'week_due_done': len(week_due.filtered(lambda t: t.state == '1_done')),
            'week_due_total': len(week_due),
            'in_process': [card(t) for t in in_process[:3]],
            'in_process_total': len(in_process),
            'projects': projects,
        }
