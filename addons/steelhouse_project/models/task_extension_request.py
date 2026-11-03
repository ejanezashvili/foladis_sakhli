from markupsafe import Markup, escape

from odoo import fields, models, _
from odoo.exceptions import UserError


class TaskExtensionRequest(models.Model):
    _name = 'steelhouse.task.extension.request'
    _description = 'ვადის გადაწევის მოთხოვნა'
    _order = 'create_date desc, id desc'

    task_id = fields.Many2one('project.task', string='დავალება', required=True, ondelete='cascade', index=True)
    requested_by_id = fields.Many2one(
        'res.users', string='მომთხოვნი', required=True, readonly=True, default=lambda self: self.env.user)
    old_deadline = fields.Datetime('მიმდინარე ვადა', readonly=True)
    new_deadline = fields.Datetime('მოთხოვნილი ვადა', required=True)
    reason = fields.Text('მიზეზი', required=True)
    state = fields.Selection([
        ('pending', 'განსახილველი'),
        ('approved', 'დადასტურებული'),
        ('rejected', 'უარყოფილი'),
    ], string='სტატუსი', default='pending', required=True, readonly=True)
    decided_by_id = fields.Many2one('res.users', string='გადაწყვიტა', readonly=True)
    decision_date = fields.Datetime('გადაწყვეტის თარიღი', readonly=True)

    def _check_can_decide(self):
        for request in self:
            if request.state != 'pending':
                raise UserError(_("ეს მოთხოვნა უკვე განხილულია."))
            if not request.task_id._sh_is_approver():
                raise UserError(_("გადაწევის მოთხოვნას განიხილავს მხოლოდ შემმოწმებელი ან პროექტის მენეჯერი."))

    def _decide(self, state):
        self.write({
            'state': state,
            'decided_by_id': self.env.user.id,
            'decision_date': fields.Datetime.now(),
        })

    def action_approve(self):
        self._check_can_decide()
        for request in self:
            task = request.task_id
            task.with_context(sh_extension_approved=True).write({
                'date_deadline': request.new_deadline,
                'deadline_extension_count': task.deadline_extension_count + 1,
            })
            request._decide('approved')
            task._sh_close_todo(task.reviewer_id, _("დადასტურდა"))
            task._sh_notify(
                request.requested_by_id,
                Markup("<b>%s</b><br/>%s: %s") % (
                    _("ვადის გადაწევა დადასტურდა."), _("ახალი ვადა"),
                    fields.Datetime.to_string(fields.Datetime.context_timestamp(task, request.new_deadline))))
        return True

    def action_reject(self):
        self._check_can_decide()
        for request in self:
            task = request.task_id
            request._decide('rejected')
            task._sh_close_todo(task.reviewer_id, _("უარყოფილია"))
            task._sh_notify(request.requested_by_id, Markup("<b>%s</b>") % _("ვადის გადაწევა უარყოფილია. ვადა უცვლელია."))
        return True

    def _post_request_message(self):
        for request in self:
            task = request.task_id
            new_local = fields.Datetime.context_timestamp(task, request.new_deadline)
            body = Markup("<b>%s</b><br/>%s: %s<br/>%s: %s") % (
                _("ვადის გადაწევის მოთხოვნა"),
                _("მოთხოვნილი ვადა"), fields.Datetime.to_string(new_local),
                _("მიზეზი"), escape(request.reason))
            task._sh_notify(task.reviewer_id, body)
            task._sh_todo(task.reviewer_id, _("ვადის გადაწევის მოთხოვნა: %s", task.name), request.reason)
