"""The "დადასტურებები" app (static/src/task_approvals): what waits for my decision as a reviewer.
A task on "შემოწმებაზე" goes to its reviewers ("შემმოწმებლები"): confirm -> done, reject with a
reason -> back to the assignee ("დაბრუნებული"). Same rules as the buttons on the task form.
The reviewer is set automatically - the person who created the task; only admins change it."""
import re

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .task_returns import _local
from .task_worktime import _fmt_secs

LATE_DAYS = 2      # waiting this many days or more is shown in red
HISTORY_LIMIT = 80


def _html_text(html):
    """Plain text of an HTML value (to tell an empty description from a filled one)."""
    return re.sub(r'<[^>]+>', '', html or '').replace('&nbsp;', ' ').strip()


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        # never without a reviewer: the creator checks the work
        for task in tasks.filtered(lambda t: not t.reviewer_ids and not t.is_template and t.project_id):
            task.sudo().with_context(sh_flow_internal=True, mail_notrack=True).reviewer_ids = [(4, self.env.uid)]
        return tasks

    def write(self, vals):
        entering = self.filtered(lambda t: t.stage_id.sh_kind != 'review') if vals.get('stage_id') else self.browse()
        res = super().write(vals)
        for task in entering.filtered(lambda t: t.stage_id.sh_kind == 'review' and not t.is_template):
            task._sh_ap_notify()
        return res

    def _sh_ap_notify(self):
        """The task went to review: its reviewers are told at once (inbox / mobile)."""
        self.ensure_one()
        users = (self.reviewer_ids or self.create_uid).filtered(lambda u: u.active and not u.share) - self.env.user
        if not users:
            return
        body = Markup('<b>%s</b><br/>%s<br/><a href="/odoo/sh-approvals">%s</a>') % (
            _("დასადასტურებელია: %s", self.display_name),
            _("დავალება გადმოვიდა შემოწმებაზე. შემსრულებლები: %s", ', '.join(self.user_ids.mapped('name')) or '-'),
            _("გახსენით „დადასტურებები“"))
        self.sudo().with_context(mail_post_autofollow=False).message_post(
            body=body, partner_ids=users.partner_id.ids, author_id=self.env.user.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')

    def _sh_apply_reason(self, kind, reason, resume_date=False):
        res = super()._sh_apply_reason(kind, reason, resume_date=resume_date)
        if not self.is_template:
            if kind == 'returned':
                self._sh_return_notify(reason)
            elif kind in ('on_hold', 'cancelled'):
                self._sh_stop_notify(kind, reason)
        return res

    def _sh_stop_notify(self, kind, reason):
        """On hold: the reviewers are told (the assignee usually puts it on hold).
        Cancelled: the assignees are told (the reviewer / admin cancels it)."""
        self.ensure_one()
        if kind == 'on_hold':
            users = self.reviewer_ids or self.create_uid
            title = _("დავალება შეჩერდა: %s", self.display_name)
            who = _("შეაჩერა: %s", self.env.user.name)
        else:
            users = self.user_ids
            title = _("დავალება გაუქმდა: %s", self.display_name)
            who = _("გააუქმა: %s", self.env.user.name)
        users = users.filtered(lambda u: u.active and not u.share) - self.env.user
        if not users:
            return
        body = Markup('<b>%s</b><br/>%s<br/>%s') % (title, _("მიზეზი: %s", reason or '-'), who)
        self.sudo().with_context(mail_post_autofollow=False).message_post(
            body=body, partner_ids=users.partner_id.ids, author_id=self.env.user.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')

    def _sh_return_notify(self, reason):
        """The task came back from review (approvals app or the stage bar): its assignees are
        told at once, with the reason - like the reviewers are told when it goes to review."""
        self.ensure_one()
        users = self.user_ids.filtered(lambda u: u.active and not u.share) - self.env.user
        if not users:
            return
        body = Markup('<b>%s</b><br/>%s<br/>%s') % (
            _("დაგიბრუნდათ შესასწორებლად: %s", self.display_name),
            _("მიზეზი: %s", reason or '-'),
            _("დააბრუნა: %s", self.env.user.name))
        self.sudo().with_context(mail_post_autofollow=False).message_post(
            body=body, partner_ids=users.partner_id.ids, author_id=self.env.user.partner_id.id,
            message_type='comment', subtype_xmlid='mail.mt_comment')

    # ------------------------------------------------------------------ data
    def _sh_ap_item(self, since, now):
        self.ensure_one()
        days = (_local(now).date() - _local(since).date()).days if since else 0
        returns = self.env['sh.task.flow.event'].sudo().search_count(
            [('task_id', '=', self.id), ('kind', '=', 'return')])
        first = self.user_ids[:1]
        return {
            'id': self.id,
            'number': self.sh_number or '',
            'name': self.name,
            'users': ', '.join(self.user_ids.mapped('name')) or '-',
            # round badge with the first assignee's initials (the colour follows the person)
            # (no .upper(): Georgian capitals are missing in many fonts)
            'initials': ''.join(w[0] for w in (first.name or '').split()[:2]),
            'color': first.id % 6,
            'reviewers': ', '.join(self.reviewer_ids.mapped('name')) or '-',
            'department': self.project_id.name or '',
            'project': self.sh_project_id.name or '',
            'deadline': _local(self.date_deadline).strftime('%d.%m.%Y') if self.date_deadline else '',
            'overdue': bool(self.date_deadline and self.date_deadline < now),
            'since': _local(since).strftime('%d.%m.%Y %H:%M') if since else '',
            'days': days,
            'wait': 'დღეს' if days <= 0 else '%d დღეა' % days,
            'late': days >= LATE_DAYS,
            'files': self.env['ir.attachment'].sudo().search_count(
                [('res_model', '=', 'project.task'), ('res_id', '=', self.id)]),
            'returns': returns,
            'work_time': _fmt_secs(self.sh_wt_secs) if self.sh_wt_secs else '',
        }

    def _sh_ap_items(self, now):
        """Tasks on review, the longest waiting first."""
        since = {}
        events = self.env['sh.task.flow.event'].sudo().search(
            [('task_id', 'in', self.ids), ('kind', '=', 'review')], order='date')
        for event in events:
            since[event.task_id.id] = event.date
        items = [task._sh_ap_item(since.get(task.id) or task.date_last_stage_update, now) for task in self]
        return sorted(items, key=lambda i: (-i['days'], i['id']))

    @api.model
    def sh_approvals_data(self, tab='todo'):
        uid = self.env.uid
        now = fields.Datetime.now()
        base = [('is_template', '=', False), ('project_id', '!=', False), ('stage_id.sh_kind', '=', 'review'),
                ('state', 'not in', ('1_done', '1_canceled'))]
        # mine to decide: I am a reviewer (a task without reviewers goes to its creator)
        todo = self.search(base + ['|', ('reviewer_ids', 'in', [uid]),
                                   '&', ('reviewer_ids', '=', False), ('create_uid', '=', uid)])
        # sent by me: my work that waits for somebody else's decision
        sent = self.search(base + ['|', ('user_ids', 'in', [uid]), ('sh_responsible_id', '=', uid)]) - todo
        data = {'counts': {'todo': len(todo), 'sent': len(sent)}, 'items': [], 'history': []}
        if tab == 'sent':
            data['items'] = sent._sh_ap_items(now)
        elif tab == 'history':
            data['history'] = self._sh_ap_history()
        else:
            data['items'] = todo._sh_ap_items(now)
            data['stats'] = {'total': len(data['items']),
                             'late': sum(1 for i in data['items'] if i['late']),
                             'overdue': sum(1 for i in data['items'] if i['overdue']),
                             'again': sum(1 for i in data['items'] if i['returns'])}
        return data

    def _sh_ap_history(self):
        """My decisions, the newest first: confirmed tasks and returns with their reasons."""
        uid = self.env.uid
        rows = []
        done = self.search([('sh_done_user_id', '=', uid), ('sh_done_date', '!=', False), ('is_template', '=', False)],
                           order='sh_done_date desc', limit=HISTORY_LIMIT)
        for task in done:
            rows.append((task.sh_done_date, {'id': task.id, 'kind': 'ok', 'number': task.sh_number or '',
                                             'name': task.name, 'users': ', '.join(task.user_ids.mapped('name')) or '-',
                                             'reason': ''}))
        events = self.env['sh.task.flow.event'].sudo().search(
            [('kind', '=', 'return'), ('user_id', '=', uid)], order='date desc', limit=HISTORY_LIMIT)
        visible = set(self.search([('id', 'in', events.task_id.ids)]).ids)  # access rules apply
        for event in events:
            task = event.task_id
            if task.id in visible:
                rows.append((event.date, {'id': task.id, 'kind': 'no', 'number': task.sh_number or '',
                                          'name': task.name, 'users': ', '.join(task.user_ids.mapped('name')) or '-',
                                          'reason': (event.reason or '').strip()}))
        rows.sort(key=lambda r: r[0], reverse=True)
        return [dict(row, date=_local(when).strftime('%d.%m.%Y %H:%M')) for when, row in rows[:HISTORY_LIMIT]]

    # ------------------------------------------------------------------ one task, for the review page
    EVENT_LABELS = {'review': 'გამოგზავნილია შემოწმებაზე', 'return': 'დაბრუნდა შესასწორებლად',
                    'hold': 'შეჩერდა', 'resume': 'გაგრძელდა', 'cancel': 'გაუქმდა'}

    def sh_approval_detail(self):
        """Everything the reviewer needs to decide without opening the task form: what was asked,
        sub-tasks, files, the way of the task (sent / returned with reasons) and the short facts."""
        self.ensure_one()
        self.check_access('read')
        now = fields.Datetime.now()
        events = self.env['sh.task.flow.event'].sudo().search([('task_id', '=', self.id)], order='date desc, id desc')
        since = events.filtered(lambda e: e.kind == 'review')[:1].date or self.date_last_stage_update
        data = self._sh_ap_item(since, now)
        uid = self.env.uid

        def who(user):
            return 'თქვენ' if user.id == uid else (user.name or '-')

        timeline = [{'kind': e.kind, 'label': self.EVENT_LABELS.get(e.kind, e.kind), 'who': who(e.user_id),
                     'date': _local(e.date).strftime('%d.%m.%Y %H:%M'), 'reason': (e.reason or '').strip()}
                    for e in events]
        timeline.append({'kind': 'create', 'label': 'დავალება შეიქმნა', 'who': who(self.create_uid),
                         'date': _local(self.create_date).strftime('%d.%m.%Y %H:%M'), 'reason': ''})
        subs = self.sudo().child_ids.filtered(lambda t: t.state != '1_canceled').sorted(lambda t: (t.sequence, t.id))
        files = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'project.task'), ('res_id', '=', self.id)], order='id desc')

        def size(num):
            num = num or 0
            return '%.1f MB' % (num / 1048576) if num >= 1048576 else '%d KB' % max(1, round(num / 1024))

        description = str(self.description or '')
        # an empty editor leaves "<p><br></p>" behind
        if not _html_text(description) and '<img' not in description:
            description = ''
        data.update({
            'description': description,
            'subtasks': [{'id': t.id, 'name': t.name, 'done': t.state == '1_done'} for t in subs],
            'subs_done': len(subs.filtered(lambda t: t.state == '1_done')),
            'files_list': [{'id': f.id, 'name': f.name, 'size': size(f.file_size),
                            'image': (f.mimetype or '').startswith('image/'),
                            'url': '/web/content/%d?download=true' % f.id} for f in files],
            'final_note': (self.sh_final_note or '').strip(),
            'timeline': timeline,
            'stage': self.stage_id.name or '',
            'in_review': self.stage_id.sh_kind == 'review' and self.state not in ('1_done', '1_canceled'),
            'can_decide': (self.stage_id.sh_kind == 'review' and self.state not in ('1_done', '1_canceled')
                           and bool(self.reviewer_ids and self.env.user in self.reviewer_ids
                                    or not self.reviewer_ids and self.create_uid.id == uid)),
        })
        return data

    # ------------------------------------------------------------------ decisions
    def _sh_ap_check(self):
        self.ensure_one()
        if self.stage_id.sh_kind != 'review':
            raise UserError(_("დავალება „%s“ აღარ არის შემოწმებაზე - სია განახლდება.", self.name))

    def sh_approval_approve(self):
        """Confirmed: the task is done (the "საბოლოო პროექტი" note can still be added on the task)."""
        self.ensure_one()
        self._sh_ap_check()
        self._sh_check_reviewer('done')
        stage = self._sh_stage_of_kind('done')
        if not stage:
            raise UserError(_("ამ დეპარტამენტს არ აქვს „დასრულებული“ სტადია."))
        self.with_context(sh_final_given=True).write({
            'stage_id': stage.id, 'sh_done_user_id': self.env.uid, 'sh_done_date': fields.Datetime.now()})
        return True

    def sh_approval_reject(self, reason):
        """Rejected: back to the assignee with the reason."""
        self.ensure_one()
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("მიუთითეთ უარყოფის მიზეზი."))
        self._sh_ap_check()
        self._sh_check_reviewer('returned')
        self._sh_apply_reason('returned', reason)
        return True
