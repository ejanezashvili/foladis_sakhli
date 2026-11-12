from markupsafe import Markup

from odoo import api, fields, models, _

CLOSED = ('1_done', '1_canceled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Overdue tasks: shown in red (kanban card / list row) and everyone on the task gets one message.
    sh_is_overdue = fields.Boolean(
        'ვადაგადაცილებული', compute='_compute_sh_is_overdue', search='_search_sh_is_overdue')
    # set once the "overdue" message was posted; cleared when the deadline changes
    sh_overdue_notified = fields.Boolean(copy=False, readonly=True)

    @api.depends('date_deadline', 'state', 'is_template')
    def _compute_sh_is_overdue(self):
        now = fields.Datetime.now()
        for task in self:
            task.sh_is_overdue = bool(task.date_deadline and task.date_deadline < now
                                      and task.state not in CLOSED and not task.is_template)

    def _search_sh_is_overdue(self, operator, value):
        domain = [('date_deadline', '!=', False), ('date_deadline', '<', fields.Datetime.now()),
                  ('state', 'not in', CLOSED), ('is_template', '=', False)]
        if operator in ('in', 'not in'):
            positive = (True in value) == (operator == 'in')
        else:
            positive = bool(value) == (operator in ('=', '=='))
        return domain if positive else ['!', '&', '&', '&'] + domain

    def write(self, vals):
        if 'date_deadline' in vals:
            vals['sh_overdue_notified'] = False
            vals['sh_escalated'] = False
        return super().write(vals)

    def _sh_overdue_people(self):
        """Everyone on the task: assignees, reviewers and the main responsible person."""
        self.ensure_one()
        return (self.user_ids | self.reviewer_ids | self.sh_responsible_id).filtered('active').partner_id

    @api.model
    def _cron_sh_overdue_notify(self):
        tasks = self.search([('sh_is_overdue', '=', True), ('sh_overdue_notified', '=', False),
                             ('project_id', '!=', False)])
        for task in tasks:
            partners = task._sh_overdue_people()
            deadline = fields.Datetime.context_timestamp(task, task.date_deadline).strftime('%d.%m.%Y %H:%M')
            body = Markup('<b>%s</b><br/>%s') % (
                _("ვადაგადაცილებულია: %s", task.display_name),
                _("დასრულების თარიღი იყო %(date)s. პასუხისმგებლები: %(people)s",
                  date=deadline, people=', '.join(partners.mapped('name')) or '-'))
            task.message_subscribe(partner_ids=partners.ids)
            task.with_context(mail_post_autofollow=False).message_post(
                body=body, partner_ids=partners.ids,
                message_type='comment', subtype_xmlid='mail.mt_comment')
            task._sh_ensure_chat()
            if task.sh_channel_id:
                task.sh_channel_id.sudo().message_post(
                    body=body, message_type='comment', subtype_xmlid='mail.mt_comment')
        tasks.with_context(sh_flow_internal=True).write({'sh_overdue_notified': True})
        tasks._sh_notify_managers()  # 4.4 reviewers + direct managers; "კრიტიკული" -> escalation at once
        self._cron_sh_escalate()     # 4.5 others: after 3 working days
