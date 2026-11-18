"""Hold and resume (შეჩერება / განახლება):

- a task taken out of "შეჩერებული" (to any stage) always lands in "ახალი" - it is accepted again;
- a whole concrete project can be put on hold (administrators / the project manager): all its open
  tasks go to "შეჩერებული"; resuming the project brings back to "ახალი" only the tasks the project
  hold stopped (a task held on its own stays held, a finished one stays finished);
- a single task on hold: only it stops. The next task(s) in its sequence get a notice and a
  "▶ გაგრძელება" button: pressing it (optional) lets them work without waiting for the held one.
"""
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

CLOSED = ('1_done', '1_canceled')
# leaving "შეჩერებული" for one of these stages = resume -> "ახალი"
RESUME_KINDS = ('new', 'accepted', 'in_progress', 'review', 'done')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # put on hold together with its project (resuming the project resumes only these)
    sh_held_by_project = fields.Boolean(copy=False, readonly=True)
    # the assignee chose to go on although a previous task is on hold
    sh_continue_ok = fields.Boolean('გაგრძელდა შეჩერებული წინა დავალების გარეშე', copy=False, readonly=True)
    sh_prev_held = fields.Boolean(compute='_compute_sh_prev_held')
    sh_prev_held_info = fields.Char(compute='_compute_sh_prev_held')

    def _sh_is_held(self):
        return self.state not in CLOSED and self.stage_id.sh_kind == 'on_hold'

    @api.depends('depend_on_ids.stage_id', 'depend_on_ids.state')
    def _compute_sh_prev_held(self):
        for task in self:
            open_prev = task.sudo().depend_on_ids.filtered(lambda t: t.state not in CLOSED)
            held = open_prev.filtered(lambda t: t._sh_is_held())
            # only when the held task(s) are all that blocks it - otherwise "გაგრძელება" would change nothing
            task.sh_prev_held = bool(held) and held == open_prev
            task.sh_prev_held_info = ', '.join(
                '%s%s%s' % (t.sh_number and t.sh_number + ' ' or '', t.name,
                            t.hold_reason and ' („%s“)' % t.hold_reason.strip() or '') for t in held)

    # ------------------------------------------------------------------ the sequence lock
    def _sh_drop_held(self, tasks):
        """With "გაგრძელება" pressed, previous tasks on hold no longer block this one."""
        self.ensure_one()
        if not self.sh_continue_ok:
            return tasks
        return tasks.filtered(lambda t: not t._sh_is_held())

    @api.depends('sh_continue_ok', 'depend_on_ids.stage_id')
    def _compute_state(self):
        super()._compute_state()
        for task in self.filtered(lambda t: t.sh_continue_ok and t.state == '04_waiting_normal'):
            if not task._sh_drop_held(task.sudo().depend_on_ids.filtered(lambda t: t.state not in CLOSED)):
                task.state = '01_in_progress'

    def is_blocked_by_dependences(self):
        if self.sh_continue_ok:
            return bool(self._sh_drop_held(self.sudo().depend_on_ids.filtered(lambda t: t.state not in CLOSED)))
        return super().is_blocked_by_dependences()

    def _sh_open_previous(self):
        return self._sh_drop_held(super()._sh_open_previous())

    def _sh_open_before_review(self):
        prev, subs = super()._sh_open_before_review()
        return self._sh_drop_held(prev), subs

    def action_sh_continue(self):
        """"▶ გაგრძელება": work on this task although the previous one is on hold."""
        self.ensure_one()
        user = self.env.user
        if not (user in self.user_ids or user == self.sh_responsible_id
                or user.has_group('project.group_project_manager')):
            raise UserError(_("გაგრძელება შეუძლია დავალების შემსრულებელს, მთავარ პასუხისმგებელს ან ადმინისტრატორს."))
        if not self.sh_prev_held:
            raise UserError(_("წინა დავალება აღარ არის შეჩერებული."))
        held = self.sh_prev_held_info
        self.sudo().with_context(sh_flow_internal=True).write({'sh_continue_ok': True})
        self.message_post(
            body=Markup('▶ <b>%s</b><br/>%s') % (
                _("გაგრძელდა შეჩერებული წინა დავალების გარეშე - %s", user.name), held),
            author_id=user.partner_id.id, message_type='notification', subtype_xmlid='mail.mt_note')
        return True

    def sh_chain_toggle_done(self, task_id):
        """The switch on a step card does not skip "განახლება": a held step is resumed first."""
        task = self._sh_chain_member(task_id)
        if task._sh_is_held():
            raise UserError(_("„%s“ შეჩერებულია - ჯერ განაახლეთ (დაბრუნდება „ახალში“).", task.name))
        return super().sh_chain_toggle_done(task_id)

    # ------------------------------------------------------------------ hold: tell the next task
    def _sh_apply_reason(self, kind, reason, resume_date=False):
        res = super()._sh_apply_reason(kind, reason, resume_date=resume_date)
        if kind == 'on_hold' and not self.is_template and not self.env.context.get('sh_project_hold'):
            self._sh_notify_next_held(reason)
        return res

    def _sh_notify_next_held(self, reason):
        self.ensure_one()
        for nxt in self.sudo().dependent_ids.filtered(lambda t: t.state not in CLOSED and not t._sh_is_held()):
            if not nxt.sh_prev_held:  # still waits for other, not held, previous tasks
                continue
            users = (nxt.user_ids | nxt.sh_responsible_id).filtered(lambda u: u.active and not u.share)
            users -= self.env.user
            if not users:
                continue
            body = Markup('<b>%s</b><br/>%s<br/>%s') % (
                _("შენი წინა დავალება შეჩერდა: %s", self.display_name),
                _("მიზეზი: %s", reason or '-'),
                _("შეგიძლია გააგრძელო შენი დავალება „%s“ - დააჭირე „▶ გაგრძელებას“ დავალებაზე. "
                  "სავალდებულო არ არის.", nxt.name))
            nxt.with_context(mail_post_autofollow=False).message_post(
                body=body, partner_ids=users.partner_id.ids, author_id=self.env.user.partner_id.id,
                message_type='comment', subtype_xmlid='mail.mt_comment')

    # ------------------------------------------------------------------ resume: always "ახალი"
    def write(self, vals):
        if (not vals.get('stage_id') or self.env.context.get('sh_flow_internal')
                or self.env.context.get('sh_resume_new')):
            return super().write(vals)
        kind = self.env['project.task.type'].browse(vals['stage_id']).sh_kind
        # cancelling / returning a held task keeps its own way; any working stage means "resume"
        resumed = self.filtered(lambda t: t.stage_id.sh_kind == 'on_hold') if kind in RESUME_KINDS else self.browse()
        if not resumed:
            return super().write(vals)
        res = True
        rest = self - resumed
        if rest:
            res = super(ProjectTask, rest).write(vals)
        # each resumed task goes to the "ახალი" stage of its own department
        for task in resumed:
            new = task._sh_stage_of_kind('new')
            task_vals = dict(vals, stage_id=(new or task.env['project.task.type'].browse(vals['stage_id'])).id)
            task_vals.pop('state', None)
            super(ProjectTask, task.with_context(sh_resume_new=True)).write(task_vals)
            task.sudo().with_context(sh_flow_internal=True).write({'sh_held_by_project': False})
            task._sh_resumed_notify()
        return res

    def _sh_resumed_notify(self):
        self.ensure_one()
        users = self.user_ids.filtered(lambda u: u.active and not u.share) - self.env.user
        body = Markup('▶ <b>%s</b>') % _("დავალება განახლდა - დაბრუნდა „ახალში“ (განაახლა: %s)", self.env.user.name)
        self.sudo().with_context(mail_post_autofollow=False).message_post(
            body=body, partner_ids=users.partner_id.ids, author_id=self.env.user.partner_id.id,
            message_type='comment' if users else 'notification',
            subtype_xmlid='mail.mt_comment' if users else 'mail.mt_note')


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sh_on_hold = fields.Boolean('შეჩერებულია', copy=False, readonly=True, tracking=True)
    sh_hold_reason = fields.Text('შეჩერების მიზეზი', copy=False, readonly=True)
    sh_hold_date = fields.Date('შეჩერების თარიღი', copy=False, readonly=True)
    sh_resume_date = fields.Date('განახლების თარიღი', copy=False, readonly=True)
    sh_can_hold = fields.Boolean(compute='_compute_sh_can_hold')

    @api.depends_context('uid')
    @api.depends('user_id')
    def _compute_sh_can_hold(self):
        admin = self.env.user.has_group('project.group_project_manager')
        for project in self:
            project.sh_can_hold = not project.sh_is_department and (admin or project.user_id == self.env.user)

    def _sh_check_can_hold(self):
        for project in self:
            if project.sh_is_department:
                raise UserError(_("დეპარტამენტს მთლიანად ვერ შეაჩერებთ - მხოლოდ კონკრეტულ პროექტს."))
            if not project.sh_can_hold:
                raise UserError(_("პროექტის შეჩერება / განახლება შეუძლია ადმინისტრატორს ან პროექტის მენეჯერს."))

    def action_sh_project_hold(self):
        self.ensure_one()
        self._sh_check_can_hold()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'steelhouse.project.hold.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': _("პროექტის შეჩერება"),
            'context': {'default_project_id': self.id},
        }

    def _sh_hold(self, reason, resume_date):
        self.ensure_one()
        self._sh_check_can_hold()
        tasks = self.env['project.task'].sudo().search([
            ('sh_project_id', '=', self.id), ('state', 'not in', CLOSED), ('is_template', '=', False)])
        tasks = tasks.filtered(lambda t: t.stage_id.sh_kind != 'on_hold')
        for task in tasks:
            if not task._sh_stage_of_kind('on_hold'):
                continue
            task.with_context(sh_project_hold=True)._sh_apply_reason(
                'on_hold', _("პროექტი შეჩერდა: %s", reason), resume_date)
            task.with_context(sh_flow_internal=True).write({'sh_held_by_project': True})
        self.sudo().write({'sh_on_hold': True, 'sh_hold_reason': reason, 'sh_resume_date': resume_date,
                           'sh_hold_date': fields.Date.context_today(self)})
        self.message_post(body=Markup('⏸ <b>%s</b><br/>%s') % (
            _("პროექტი შეჩერდა (%s დავალება)", len(tasks)), _("მიზეზი: %s", reason)))
        return True

    def action_sh_project_resume(self):
        self.ensure_one()
        self._sh_check_can_hold()
        tasks = self.env['project.task'].sudo().search([
            ('sh_project_id', '=', self.id), ('sh_held_by_project', '=', True), ('state', 'not in', CLOSED)])
        tasks = tasks.filtered(lambda t: t.stage_id.sh_kind == 'on_hold')
        for task in tasks:
            new = task._sh_stage_of_kind('new')
            if new:
                task.write({'stage_id': new.id})
        self.env['project.task'].sudo().search([('sh_project_id', '=', self.id), ('sh_held_by_project', '=', True)]) \
            .with_context(sh_flow_internal=True).write({'sh_held_by_project': False})
        self.sudo().write({'sh_on_hold': False, 'sh_resume_date': fields.Date.context_today(self)})
        self.message_post(body=Markup('▶ <b>%s</b>') % _("პროექტი განახლდა - %s დავალება დაბრუნდა „ახალში“", len(tasks)))
        return True


class ProjectHoldWizard(models.TransientModel):
    _name = 'steelhouse.project.hold.wizard'
    _description = 'პროექტის შეჩერება'

    project_id = fields.Many2one('project.project', required=True, ondelete='cascade')
    reason = fields.Text('შეჩერების მიზეზი', required=True)
    resume_date = fields.Date('განახლების თარიღი')

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or '').strip():
            raise UserError(_("მიუთითეთ მიზეზი."))
        self.project_id._sh_hold(self.reason.strip(), self.resume_date)
        return {'type': 'ir.actions.act_window_close'}
