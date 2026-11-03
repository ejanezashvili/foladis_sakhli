from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Our stages (xml id suffix -> key). Keys are used by buttons and views.
STAGE_KEYS = ['new', 'accepted', 'in_progress', 'on_hold', 'review', 'returned', 'done', 'cancelled']

# Odoo task state that matches each of our stages.
STAGE_STATE = {
    'done': '1_done',
    'cancelled': '1_canceled',
    'returned': '02_changes_requested',
}
CLOSED_STATES = ('1_done', '1_canceled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    responsible_id = fields.Many2one(
        'res.users', string='მთავარი პასუხისმგებელი', tracking=True, index=True,
        domain="[('share', '=', False)]",
        help="ერთი მთავარი პასუხისმგებელი. დანარჩენი შემსრულებლები მონაწილეები არიან.")
    reviewer_id = fields.Many2one(
        'res.users', string='შემმოწმებელი', tracking=True, index=True, copy=False,
        default=lambda self: self.env.user, domain="[('share', '=', False)]",
        help="ადასტურებს შესრულებას, ვადის გადაწევას, აბრუნებს ან აუქმებს დავალებას.")
    sh_stage_key = fields.Selection(
        [(k, k) for k in STAGE_KEYS], compute='_compute_sh_stage_key', store=True, index=True,
        string='სტადიის კოდი')

    # Deadlines
    date_deadline_original = fields.Datetime('თავდაპირველი ვადა', readonly=True, copy=False)
    deadline_extension_count = fields.Integer('ვადის გადაწევების რაოდენობა', readonly=True, copy=False)
    extension_request_ids = fields.One2many(
        'steelhouse.task.extension.request', 'task_id', string='ვადის გადაწევის მოთხოვნები', copy=False)
    has_pending_extension = fields.Boolean(
        'გადაწევის მოთხოვნა განსახილველია', compute='_compute_has_pending_extension', store=True)
    deadline_reminder_sent = fields.Boolean(copy=False, readonly=True)
    overdue_notified = fields.Boolean(copy=False, readonly=True)

    # Execution
    evidence_required = fields.Boolean(
        'საჭიროა მტკიცებულება', help="შემოწმებაზე გაგზავნამდე უნდა მიმაგრდეს ფაილი ან ფოტო.")
    hold_reason = fields.Text('შეჩერების მიზეზი', copy=False, tracking=True)
    resume_date = fields.Date('განახლების თარიღი', copy=False, tracking=True)
    last_return_reason = fields.Text('დაბრუნების მიზეზი', copy=False, tracking=True)
    return_count = fields.Integer('დაბრუნებების რაოდენობა', readonly=True, copy=False)
    cancel_reason = fields.Text('გაუქმების მიზეზი', copy=False, tracking=True)

    # Results (for reports)
    date_done = fields.Datetime('დასრულების თარიღი', readonly=True, copy=False)
    done_on_time = fields.Boolean(
        'დროულად შესრულდა', compute='_compute_done_on_time', store=True,
        help="დასრულდა მიმდინარე ვადაში (გადაწევის ჩათვლით).")
    done_within_original = fields.Boolean(
        'თავდაპირველ ვადაში შესრულდა', compute='_compute_done_on_time', store=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    def _sh_stage(self, key):
        return self.env.ref(f'steelhouse_project.stage_{key}', raise_if_not_found=False)

    def _sh_stage_map(self):
        """{stage_id: key} for our stages that exist."""
        res = {}
        for key in STAGE_KEYS:
            stage = self._sh_stage(key)
            if stage:
                res[stage.id] = key
        return res

    @api.depends('stage_id')
    def _compute_sh_stage_key(self):
        stage_map = self._sh_stage_map()
        for task in self:
            task.sh_stage_key = stage_map.get(task.stage_id.id, False)

    @api.depends('extension_request_ids.state')
    def _compute_has_pending_extension(self):
        for task in self:
            task.has_pending_extension = any(r.state == 'pending' for r in task.extension_request_ids)

    @api.depends('date_done', 'date_deadline', 'date_deadline_original')
    def _compute_done_on_time(self):
        for task in self:
            done = task.date_done
            task.done_on_time = bool(done and (not task.date_deadline or done <= task.date_deadline))
            original = task.date_deadline_original or task.date_deadline
            task.done_within_original = bool(done and (not original or done <= original))

    # ------------------------------------------------------------------
    # Rights
    # ------------------------------------------------------------------
    def _sh_is_approver(self):
        """Reviewer, project manager, or anyone if no reviewer is set."""
        self.ensure_one()
        user = self.env.user
        return (
            self.env.su
            or not self.reviewer_id
            or self.reviewer_id == user
            or user.has_group('project.group_project_manager')
        )

    def _sh_check_approver(self, action_label):
        for task in self:
            if not task._sh_is_approver():
                raise UserError(_(
                    "„%(action)s“ შეუძლია მხოლოდ შემმოწმებელს (%(reviewer)s) ან პროექტის მენეჯერს.",
                    action=action_label, reviewer=task.reviewer_id.name))

    def _sh_check_assignee(self, action_label):
        user = self.env.user
        for task in self:
            if self.env.su or user.has_group('project.group_project_manager'):
                continue
            if user not in task.user_ids and user != task.responsible_id and user != task.reviewer_id:
                raise UserError(_("„%(action)s“ შეუძლია მხოლოდ დავალების შემსრულებელს.", action=action_label))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date_deadline') and not vals.get('date_deadline_original'):
                vals['date_deadline_original'] = vals['date_deadline']
        tasks = super().create(vals_list)
        for task in tasks:
            if not task.responsible_id and task.user_ids:
                task.responsible_id = task.user_ids[:1]
        return tasks

    def write(self, vals):
        skip = self.env.su or self.env.context.get('sh_skip_checks')
        vals = dict(vals)

        # Stage drag & drop: keep Odoo state in line with our stage.
        if vals.get('stage_id') and 'state' not in vals:
            key = self._sh_stage_map().get(vals['stage_id'])
            if key:
                vals['state'] = STAGE_STATE.get(key, '01_in_progress')

        if not skip:
            regular = self.filtered(lambda t: not t.is_template)
            if vals.get('state') == '1_done':
                regular._sh_check_approver(_("დასრულება"))
            if vals.get('state') == '1_canceled':
                regular._sh_check_approver(_("გაუქმება"))
            if 'date_deadline' in vals and not self.env.context.get('sh_extension_approved'):
                for task in regular.filtered('date_deadline'):
                    if not task._sh_is_approver():
                        raise UserError(_(
                            "ვადის შესაცვლელად გამოიყენეთ ღილაკი „ვადის გადაწევის მოთხოვნა“. "
                            "ვადას პირდაპირ ცვლის მხოლოდ შემმოწმებელი."))

        if 'date_deadline' in vals:
            vals.setdefault('deadline_reminder_sent', False)
            vals.setdefault('overdue_notified', False)
        if 'state' in vals:
            if vals['state'] == '1_done':
                vals.setdefault('date_done', fields.Datetime.now())
            elif vals['state'] not in CLOSED_STATES:
                vals.setdefault('date_done', False)

        res = super().write(vals)

        if vals.get('date_deadline'):
            self.filtered(lambda t: not t.date_deadline_original).sudo().with_context(
                sh_skip_checks=True).write({'date_deadline_original': vals['date_deadline']})
        if 'user_ids' in vals:
            for task in self.filtered(lambda t: not t.responsible_id and t.user_ids):
                task.sudo().with_context(sh_skip_checks=True).responsible_id = task.user_ids[:1]
        return res

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sh_move(self, key, extra_vals=None):
        """Move to one of our stages (if the project uses it) and write extra values."""
        stage = self._sh_stage(key)
        for task in self:
            vals = dict(extra_vals or {})
            if stage and stage in task.project_id.type_ids:
                vals['stage_id'] = stage.id
            if key in STAGE_STATE:
                vals['state'] = STAGE_STATE[key]
            elif 'state' not in vals and task.state in CLOSED_STATES + ('02_changes_requested',):
                vals['state'] = '01_in_progress'
            task.with_context(sh_skip_checks=True).write(vals)

    def _sh_notify(self, users, body):
        """Post a message on the task and notify the given users."""
        partners = users.filtered(lambda u: u and u != self.env.user).partner_id
        self.message_post(
            body=body, partner_ids=partners.ids,
            message_type='comment', subtype_xmlid='mail.mt_comment')

    def _sh_todo(self, user, summary, note=''):
        if user:
            self.activity_schedule(
                'mail.mail_activity_data_todo', summary=summary, note=note, user_id=user.id,
                date_deadline=fields.Date.context_today(self))

    def _sh_close_todo(self, user, feedback=''):
        if user:
            self.activity_feedback(['mail.mail_activity_data_todo'], user_id=user.id, feedback=feedback)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_sh_accept(self):
        self._sh_check_assignee(_("მიღება"))
        for task in self:
            task._sh_move('accepted')
            task._sh_notify(task.reviewer_id, _("დავალება მიღებულია: %s", self.env.user.name))
        return True

    def action_sh_start(self):
        self._sh_check_assignee(_("დაწყება"))
        self._sh_move('in_progress')
        return True

    def action_sh_resume(self):
        self._sh_check_assignee(_("განახლება"))
        for task in self:
            task._sh_move('in_progress', {'hold_reason': False, 'resume_date': False})
            task._sh_notify(task.reviewer_id, _("დავალება განახლდა: %s", self.env.user.name))
        return True

    def action_sh_submit_review(self):
        self._sh_check_assignee(_("შემოწმებაზე გაგზავნა"))
        Attachment = self.env['ir.attachment'].sudo()
        for task in self:
            if task.evidence_required and not Attachment.search_count(
                    [('res_model', '=', 'project.task'), ('res_id', '=', task.id)]):
                raise UserError(_(
                    "ამ დავალებას სჭირდება მტკიცებულება. მიამაგრეთ ფაილი ან ფოტო "
                    "(ქვემოთ, კომენტარების ველში) და შემდეგ გააგზავნეთ შემოწმებაზე."))
            task._sh_move('review')
            task._sh_todo(task.reviewer_id, _("შესამოწმებელია: %s", task.name))
            task._sh_notify(task.reviewer_id, _("დავალება გაიგზავნა შემოწმებაზე."))
        return True

    def action_sh_approve(self):
        self._sh_check_approver(_("დადასტურება"))
        for task in self:
            task._sh_move('done')
            task._sh_close_todo(task.reviewer_id, _("დადასტურდა"))
            task._sh_notify(task.user_ids | task.responsible_id, _("დავალება დადასტურდა და დასრულდა."))
        return True

    def _sh_open_reason_wizard(self, mode):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'steelhouse.task.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_ids': self.ids, 'default_mode': mode},
        }

    def action_sh_return(self):
        self._sh_check_approver(_("დაბრუნება"))
        return self._sh_open_reason_wizard('return')

    def action_sh_hold(self):
        self._sh_check_assignee(_("შეჩერება"))
        return self._sh_open_reason_wizard('hold')

    def action_sh_cancel(self):
        self._sh_check_approver(_("გაუქმება"))
        return self._sh_open_reason_wizard('cancel')

    def action_sh_request_extension(self):
        self.ensure_one()
        self._sh_check_assignee(_("ვადის გადაწევის მოთხოვნა"))
        if self.has_pending_extension:
            raise UserError(_("ამ დავალებაზე უკვე არის განსახილველი გადაწევის მოთხოვნა."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'steelhouse.task.extension.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id},
        }

    # ------------------------------------------------------------------
    # Cron: deadline reminders and overdue notifications
    # ------------------------------------------------------------------
    @api.model
    def _cron_sh_deadline_notifications(self):
        now = fields.Datetime.now()
        base = [('is_closed', '=', False), ('is_template', '=', False), ('date_deadline', '!=', False)]

        soon = self.search(base + [
            ('deadline_reminder_sent', '=', False),
            ('date_deadline', '>', now),
            ('date_deadline', '<=', now + timedelta(days=1)),
        ])
        for task in soon:
            task._sh_notify(
                task.user_ids | task.responsible_id,
                _("შეხსენება: დავალების ვადა იწურება 24 საათში."))
        soon.with_context(sh_skip_checks=True).write({'deadline_reminder_sent': True})

        late = self.search(base + [('overdue_notified', '=', False), ('date_deadline', '<', now)])
        for task in late:
            boss = task.reviewer_id or task.create_uid
            task._sh_notify(
                (task.user_ids | task.responsible_id | boss),
                Markup("<b>%s</b>") % _("დავალების ვადა გადაცილებულია."))
            task._sh_todo(boss, _("ვადაგადაცილებული: %s", task.name))
        late.with_context(sh_skip_checks=True).write({'overdue_notified': True})

    def _sh_reason_html(self, title, reason, extra=''):
        body = Markup("<b>%s</b><br/>%s") % (title, escape(reason or ''))
        if extra:
            body += Markup("<br/>%s") % extra
        return body
