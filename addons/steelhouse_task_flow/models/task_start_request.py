"""„დაწყების მოთხოვნა“: the performer of a task that waits for previous ones asks their people
to let it start.

The request only tells: a note with a notification goes to the performers, main responsible and
reviewers of every previous task that is still open. The rule itself does not change - the next
task starts when the previous one is finished, or, when it is on hold, with "▶ შემდეგის დაშვება"
(models/task_hold.py); a step can also be moved in the "თანმიმდევრობა" tab.
"""
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

CLOSED = ('1_done', '1_canceled')
# the same person cannot ask again sooner than this
AGAIN_AFTER = timedelta(hours=1)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_start_request_date = fields.Datetime('დაწყება მოთხოვნილია', copy=False, readonly=True)
    sh_can_request_start = fields.Boolean(compute='_compute_sh_can_request_start')

    @api.depends('state', 'user_ids', 'sh_responsible_id', 'depend_on_ids.state', 'sh_continue_ok')
    @api.depends_context('uid')
    def _compute_sh_can_request_start(self):
        user = self.env.user
        for task in self:
            task.sh_can_request_start = bool(
                task.id and not task.is_template and task.state not in CLOSED
                and not task._sh_is_main()      # the main task waits for nobody: its steps are its own parts
                and user in (task.user_ids | task.sh_responsible_id)
                and task._sh_open_previous())

    def action_sh_request_start(self):
        """Asks the people of the open previous tasks to finish them or to let this one start."""
        self.ensure_one()
        user = self.env.user
        if user not in (self.user_ids | self.sh_responsible_id):
            raise UserError(_("დაწყების მოთხოვნა შეუძლია ამ დავალების შემსრულებელს ან მთავარ პასუხისმგებელს."))
        prev = self.browse() if self._sh_is_main() else self._sh_open_previous()
        if not prev:
            raise UserError(_("დავალება აღარ ელოდება წინა დავალებებს - შეგიძლიათ დაიწყოთ."))
        now = fields.Datetime.now()
        if self.sh_start_request_date and now - self.sh_start_request_date < AGAIN_AFTER:
            raise UserError(_("მოთხოვნა უკვე გაგზავნილია. ხელახლა გაგზავნა შეიძლება ერთი საათის შემდეგ."))
        me = self.sudo()
        asked = self.env['res.users']
        for task in prev:
            users = (task.user_ids | task.sh_responsible_id | task.reviewer_ids).filtered(
                lambda u: u.active and not u.share) - user
            asked |= users
            if task._sh_is_held():
                hint = _("თქვენი დავალება შეჩერებულია: თუ შემდეგი საქმე მის გარეშეც შეიძლება დაიწყოს, "
                         "დააჭირეთ „▶ შემდეგის დაშვება“.")
            else:
                hint = _("დაასრულეთ დავალება, ან, თუ ახლა ვერ სრულდება, გადაიყვანეთ „შეჩერებულზე“ "
                         "და დააჭირეთ „▶ შემდეგის დაშვება“.")
            task.with_context(mail_post_autofollow=False).message_post(
                body=Markup('🙋 <b>%s</b><br/>%s<br/>%s') % (
                    _("%s ითხოვს შემდეგი დავალების დაწყებას", user.name), self._sh_label(me), hint),
                partner_ids=users.partner_id.ids, author_id=user.partner_id.id,
                message_type='comment' if users else 'notification',
                subtype_xmlid='mail.mt_comment' if users else 'mail.mt_note')
        me.with_context(sh_flow_internal=True).write({'sh_start_request_date': now})
        me.message_post(
            body=Markup('🙋 <b>%s</b><br/>%s') % (
                _("დაწყების მოთხოვნა გაიგზავნა: %s", ', '.join(asked.mapped('name')) or '-'),
                ', '.join(self._sh_label(t) for t in prev)),
            author_id=user.partner_id.id, message_type='notification', subtype_xmlid='mail.mt_note')
        return True
