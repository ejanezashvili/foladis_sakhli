"""Block 4 notifications that need more than a plain automation rule:
- 4.4 delay -> reviewers + the assignees' direct managers (activity)
- 4.5 escalation -> the managers of those managers: "კრიტიკული" at once, others after 3 working days
- 4.9 weekly summary -> each employee (own tasks) and each department head (department), first working day of the week
Working days follow the company calendar with its public holidays (Asia/Tbilisi)."""
from datetime import datetime, time, timedelta

import pytz
from markupsafe import Markup

from odoo import api, fields, models

CLOSED = ('1_done', '1_canceled')
ESCALATE_AFTER_DAYS = 3
TODO = 'mail.mail_activity_data_todo'


class ResUsers(models.Model):
    _inherit = 'res.users'

    # e-mail is not set up yet: new users get their notifications in Odoo (inbox / mobile)
    notification_type = fields.Selection(default='inbox')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # set once the escalation went out; cleared when the deadline changes (see task_overdue.write)
    sh_escalated = fields.Boolean(copy=False, readonly=True)

    # ------------------------------------------------------------------ helpers
    def _sh_employees(self, users):
        return self.env['hr.employee'].sudo().search([('user_id', 'in', users.ids)]) if users else self.env['hr.employee']

    def _sh_direct_managers(self):
        """Users who are the direct manager (structure) of the task's assignees."""
        self.ensure_one()
        return self._sh_employees(self.user_ids).parent_id.user_id.filtered('active')

    def _sh_first_level(self):
        """4.4: reviewers (no reviewer -> the creator) and the assignees' direct managers."""
        self.ensure_one()
        return ((self.reviewer_ids or self.create_uid) | self._sh_direct_managers()).filtered(
            lambda u: u.active and not u.share)

    def _sh_escalation_users(self):
        """One level up: all equal heads of the 4.4 people."""
        self.ensure_one()
        first = self._sh_first_level()
        top = self._sh_employees(first).sh_manager_ids.user_id.filtered('active')
        return top - first - self.user_ids

    def _sh_schedule(self, users, summary, note):
        for user in users:
            already = self.activity_ids.filtered(lambda a: a.user_id == user and a.summary == summary)
            if not already:
                self.sudo().activity_schedule(TODO, user_id=user.id, summary=summary, note=note)

    def _sh_people_note(self):
        return 'შემსრულებლები: %s; შემმოწმებლები: %s; ვადა: %s' % (
            ', '.join(self.user_ids.mapped('name')) or '-', ', '.join(self.reviewer_ids.mapped('name')) or '-',
            fields.Datetime.context_timestamp(self, self.date_deadline).strftime('%d.%m.%Y') if self.date_deadline else '-')

    # ------------------------------------------------------------------ 4.4 / 4.5
    def _sh_notify_managers(self):
        """Called once when the task becomes overdue (from the hourly overdue cron)."""
        for task in self:
            label = '%s%s' % (task.sh_number and task.sh_number + ' ' or '', task.name)
            task._sh_schedule(task._sh_first_level() - task.user_ids,
                              'ვადაგადაცილებულია: %s' % label, task._sh_people_note())
            if task.priority == '3':
                task._sh_escalate(critical=True)

    def _sh_escalate(self, critical=False):
        for task in self:
            label = '%s%s' % (task.sh_number and task.sh_number + ' ' or '', task.name)
            why = 'კრიტიკული დავალება ვადაგადაცილებულია' if critical else \
                '%s სამუშაო დღით ვადაგადაცილებული' % ESCALATE_AFTER_DAYS
            task._sh_schedule(task._sh_escalation_users(), 'ესკალაცია - %s: %s' % (why, label), task._sh_people_note())
            task.with_context(sh_flow_internal=True).sh_escalated = True

    def _sh_calendar(self):
        return self.env.company.sudo().resource_calendar_id

    def _sh_working_days_between(self, start, end):
        cal = self._sh_calendar()
        if not cal or end <= start:
            return (end - start).days
        data = cal.get_work_duration_data(pytz.utc.localize(start), pytz.utc.localize(end), compute_leaves=True)
        return data['days']

    @api.model
    def _cron_sh_escalate(self):
        now = fields.Datetime.now()
        tasks = self.search([('sh_is_overdue', '=', True), ('sh_overdue_notified', '=', True),
                             ('sh_escalated', '=', False), ('project_id', '!=', False)])
        late = tasks.filtered(lambda t: t._sh_working_days_between(t.date_deadline, now) >= ESCALATE_AFTER_DAYS)
        late._sh_escalate()

    # ------------------------------------------------------------------ 4.9 weekly summary
    def _sh_is_working_day(self, day):
        cal = self._sh_calendar()
        if not cal:
            return day.weekday() < 5
        tz = pytz.timezone(cal.tz or 'Asia/Tbilisi')
        start = tz.localize(datetime.combine(day, time.min))
        return cal.get_work_hours_count(start, start + timedelta(days=1), compute_leaves=True) > 0

    @api.model
    def _cron_sh_weekly_digest(self):
        """Runs daily at 09:00; sends once a week, on its first working day (holiday Monday -> Tuesday)."""
        tz = pytz.timezone(self._sh_calendar().tz or 'Asia/Tbilisi')
        today = datetime.now(tz).date()
        week = '%s-W%02d' % today.isocalendar()[:2]
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('steelhouse_task_flow.digest_week') == week or not self._sh_is_working_day(today):
            return
        self._sh_send_weekly_digest(today)
        params.set_param('steelhouse_task_flow.digest_week', week)

    def _sh_digest_url(self, task):
        return '/odoo/project.task/%d' % task.id

    def _sh_digest_rows(self, tasks, now, late=False):
        rows = []
        for t in tasks.sorted(lambda t: (t.date_deadline or datetime.max)):
            deadline = fields.Datetime.context_timestamp(t, t.date_deadline).strftime('%d.%m') if t.date_deadline else '-'
            days = (now - t.date_deadline).days if late and t.date_deadline else None
            extra = '' if days is None else (' (დღეს)' if days == 0 else ' (%d დღე)' % days)
            rows.append(Markup('<li><a href="%s">%s%s</a> - %s%s</li>') % (
                self._sh_digest_url(t), t.sh_number and t.sh_number + ' ' or '', t.name, deadline, extra))
        return Markup('<ul>%s</ul>') % Markup('').join(rows) if rows else ''

    def _sh_digest_section(self, title, tasks, now, late=False, limit=15):
        if not tasks:
            return ''
        more = len(tasks) - limit
        body = self._sh_digest_rows(tasks[:limit] if more > 0 else tasks, now, late)
        tail = Markup('<p>... და კიდევ %d</p>') % more if more > 0 else ''
        return Markup('<p><b>%s (%d)</b></p>%s%s') % (title, len(tasks), body, tail)

    def _sh_send_weekly_digest(self, today):
        now = fields.Datetime.now()
        week_ago = now - timedelta(days=7)
        week_end = now + timedelta(days=7)
        Task = self.sudo().with_context(active_test=True)
        base = [('is_template', '=', False), ('project_id', '!=', False)]
        open_tasks = Task.search(base + [('state', 'not in', CLOSED)])
        done_week = Task.search(base + [('state', '=', '1_done'), ('date_last_stage_update', '>=', week_ago)])
        period = '%s - %s' % ((today - timedelta(days=7)).strftime('%d.%m'), (today - timedelta(days=1)).strftime('%d.%m'))

        # employees: own tasks
        users = (open_tasks.user_ids | open_tasks.reviewer_ids | done_week.user_ids).filtered(
            lambda u: u.active and not u.share)
        for user in users:
            mine = open_tasks.filtered(lambda t: user in t.user_ids)
            overdue = mine.filtered(lambda t: t.date_deadline and t.date_deadline < now)
            due = mine.filtered(lambda t: t.date_deadline and now <= t.date_deadline < week_end)
            review = open_tasks.filtered(lambda t: user in t.reviewer_ids and t.stage_id.sh_kind == 'review')
            done = done_week.filtered(lambda t: user in t.user_ids)
            if not (mine or review or done):
                continue
            body = Markup('<p><b>კვირის შეჯამება (%s)</b></p>'
                          '<p>✅ გასულ კვირას დაასრულე: <b>%d</b> &nbsp; 📋 ღია დავალება: <b>%d</b> &nbsp; '
                          '⏰ ვადაგადაცილებული: <b>%d</b></p>') % (period, len(done), len(mine), len(overdue))
            body += self._sh_digest_section('⏰ ვადაგადაცილებული', overdue, now, late=True)
            body += self._sh_digest_section('📅 ამ კვირის ვადით', due, now)
            body += self._sh_digest_section('🔎 შენს დადასტურებას ელოდება', review, now)
            self._sh_digest_post(user, 'კვირის შეჯამება: %s' % period, body)

        # department heads: their department (and sub-departments)
        depts = self.env['hr.department'].sudo().search([('manager_ids', '!=', False)])
        heads = {}
        for dept in depts:
            for emp in dept.manager_ids.filtered(lambda e: e.user_id.active):
                heads.setdefault(emp.user_id, self.env['hr.department'])
                heads[emp.user_id] |= dept
        for user, mine_depts in heads.items():
            dom = [('sh_department_id', 'child_of', mine_depts.ids)]
            d_open = open_tasks.filtered_domain(dom)
            d_done = done_week.filtered_domain(dom)
            d_new = Task.search(base + dom + [('create_date', '>=', week_ago)])
            if not (d_open or d_done or d_new):
                continue
            d_over = d_open.filtered(lambda t: t.date_deadline and t.date_deadline < now)
            d_review = d_open.filtered(lambda t: t.stage_id.sh_kind == 'review')
            rows = []
            for emp_user in (d_open | d_done).user_ids.sorted('name'):
                o = d_open.filtered(lambda t: emp_user in t.user_ids)
                rows.append(Markup('<tr><td>%s</td><td style="text-align:center">%d</td>'
                                   '<td style="text-align:center">%d</td><td style="text-align:center">%d</td></tr>') % (
                    emp_user.name, len(o), len(o.filtered(lambda t: t in d_over)),
                    len(d_done.filtered(lambda t: emp_user in t.user_ids))))
            table = Markup('<table class="table table-sm table-bordered"><tr><th>თანამშრომელი</th><th>ღია</th>'
                           '<th>ვადაგადაცილ.</th><th>დასრულდა</th></tr>%s</table>') % Markup('').join(rows)
            body = Markup('<p><b>დეპარტამენტის კვირის შეჯამება (%s): %s</b></p>'
                          '<p>🆕 ახალი: <b>%d</b> &nbsp; ✅ დასრულდა: <b>%d</b> &nbsp; 📋 ღია: <b>%d</b> &nbsp; '
                          '⏰ ვადაგადაცილებული: <b>%d</b> &nbsp; 🔎 შემოწმებაზე: <b>%d</b></p>') % (
                period, ', '.join(mine_depts.mapped('name')), len(d_new), len(d_done), len(d_open),
                len(d_over), len(d_review))
            body += table
            body += self._sh_digest_section('⏰ ყველაზე დაგვიანებული', d_over.sorted('date_deadline'), now, late=True, limit=10)
            self._sh_digest_post(user, 'დეპარტამენტის კვირის შეჯამება: %s' % period, body)

    def _sh_digest_post(self, user, subject, body):
        """Private OdooBot chat message (inbox / mobile push, e-mail for users who chose e-mail)."""
        bot = self.env.ref('base.user_root')
        Channel = self.env['discuss.channel'].with_user(bot).sudo()
        chat = Channel.search([('channel_type', '=', 'chat'),
                               ('channel_member_ids.partner_id', '=', user.partner_id.id),
                               ('channel_member_ids.partner_id', '=', bot.partner_id.id)], limit=1)
        if not chat:
            chat = Channel.create({
                'name': '%s, %s' % (bot.partner_id.name, user.partner_id.name), 'channel_type': 'chat',
                'channel_member_ids': [(0, 0, {'partner_id': bot.partner_id.id}),
                                       (0, 0, {'partner_id': user.partner_id.id})]})
        chat.message_post(body=body, subject=subject, author_id=bot.partner_id.id,
                          message_type='comment', subtype_xmlid='mail.mt_comment')
