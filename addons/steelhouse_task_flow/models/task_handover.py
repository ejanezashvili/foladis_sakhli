"""Handing a task over: the main responsible is changed right in the field "მთავარი პასუხისმგებელი"
- for instance when he was chosen by mistake.

- Who may: the current main responsible, an assignee, a reviewer or an administrator. An assignee
  may change this one field only (the rest of the task stays locked - task_edit_lock.py).
- The former responsible stops seeing the task - unless he still takes part in the job (assignee,
  reviewer, creator, another step) - and leaves its shared chat.
- Every change of the main responsible, whichever way it was made, is kept in
  `steelhouse.task.responsible.change` (who, when, from whom, to whom): the report
  "რეპორტინგი - პასუხისმგებლის ცვლილებები". Setting the first responsible is not a change.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TaskResponsibleChange(models.Model):
    _name = 'steelhouse.task.responsible.change'
    _description = 'მთავარი პასუხისმგებლის ცვლილება'
    _order = 'date desc, id desc'
    _rec_name = 'task_id'

    task_id = fields.Many2one('project.task', string='დავალება', required=True, ondelete='cascade', index=True)
    project_id = fields.Many2one(related='task_id.project_id', string='დეპარტამენტი', store=True, index=True)
    date = fields.Datetime('როდის', required=True, default=fields.Datetime.now, index=True)
    user_id = fields.Many2one('res.users', string='ვინ შეცვალა', index=True)
    old_user_id = fields.Many2one('res.users', string='ვისგან', index=True)
    new_user_id = fields.Many2one('res.users', string='ვისზე', index=True)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_can_handover = fields.Boolean(compute='_compute_sh_can_handover')

    def _sh_can_handover(self):
        self.ensure_one()
        return self._sh_can_edit() or self.env.user in self.user_ids

    @api.depends('sh_responsible_id', 'reviewer_ids', 'user_ids')
    @api.depends_context('uid')
    def _compute_sh_can_handover(self):
        for task in self:
            # a task that is not saved yet: whoever creates it chooses the responsible
            task.sh_can_handover = not task._origin.id or task._sh_can_handover()

    def _sh_handover(self, new_user):
        """Give the task to `new_user`. Runs as superuser after the check: the one who hands the
        task over may lose sight of it in the middle of the save."""
        self.ensure_one()
        if not self._sh_can_handover():
            raise UserError(_("მთავარი პასუხისმგებლის შეცვლა შეუძლია მხოლოდ მთავარ პასუხისმგებელს, "
                              "შემსრულებელს, შემმოწმებელს ან ადმინისტრატორს."))
        task = self.sudo()
        if new_user.share or not new_user.active:
            raise UserError(_("აირჩიეთ თანამშრომელი."))
        task.write({'sh_responsible_id': new_user.id})
        if new_user != self.env.user:
            label = '%s%s' % (task.sh_number and task.sh_number + ' ' or '', task.name)
            task.message_notify(
                partner_ids=new_user.partner_id.ids,
                subject=_("თქვენ გახდით მთავარი პასუხისმგებელი: %s", label),
                body=Markup("%s") % _("%(who)s-მა დავალება „%(task)s“ თქვენ გადმოგაწერათ.",
                                      who=self.env.user.name, task=label))

    def _sh_leave_chat(self, user):
        """The former responsible leaves the shared chat when he is no longer on the task."""
        self.ensure_one()
        task = self.sudo()
        channel = task.sh_channel_id
        if channel and user.partner_id not in task._sh_chat_partners():
            channel.channel_member_ids.filtered(lambda m: m.partner_id == user.partner_id).unlink()

    def web_save(self, vals, specification, *args, **kwargs):
        """The field changed on the form: the new responsible is set apart from the rest of the
        save - an assignee may change nothing else, and the one who gives the task away may no
        longer be allowed to read it back."""
        new_id = vals.get('sh_responsible_id')
        if not (len(self) == 1 and new_id and not self._sh_is_edit_admin()
                and new_id != self.sudo().sh_responsible_id.id):
            return super().web_save(vals, specification, *args, **kwargs)
        vals = {k: v for k, v in vals.items() if k != 'sh_responsible_id'}
        res = super().web_save(vals, specification, *args, **kwargs)
        self._sh_handover(self.env['res.users'].browse(new_id))
        if kwargs.get('next_id'):
            return res
        # no longer mine: shown once more as saved; it is gone from my lists after that
        task = self if self.has_access('read') else self.sudo()
        return task.web_read(specification)

    def write(self, vals):
        before = {}
        if 'sh_responsible_id' in vals:
            before = {t.id: t.sh_responsible_id for t in self.sudo()}
        res = super().write(vals)
        if before:
            Change = self.env['steelhouse.task.responsible.change'].sudo()
            for task in self.sudo():
                old = before.get(task.id)
                if not old or old == task.sh_responsible_id or task.is_template or not task.project_id:
                    continue
                Change.create({'task_id': task.id, 'user_id': self.env.uid, 'old_user_id': old.id,
                               'new_user_id': task.sh_responsible_id.id})
                task._sh_leave_chat(old)
        return res
