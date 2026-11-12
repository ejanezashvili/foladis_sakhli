from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # kanban card footer: number of comments (messages written by people, not system notes)
    sh_comment_count = fields.Integer('კომენტარები', compute='_compute_sh_comment_count')

    def _compute_sh_comment_count(self):
        counts = {}
        if self.ids:
            groups = self.env['mail.message'].sudo()._read_group(
                [('model', '=', 'project.task'), ('res_id', 'in', self.ids), ('message_type', '=', 'comment')],
                ['res_id'], ['__count'])
            counts = {res_id: count for res_id, count in groups}
        for task in self:
            task.sh_comment_count = counts.get(task.id, 0)

    # kanban card: deadline as plain text "17.11.2026" in the user's time zone (formatted on the server)
    sh_deadline_str = fields.Char(compute='_compute_sh_deadline_str')

    def _compute_sh_deadline_str(self):
        for task in self:
            task.sh_deadline_str = fields.Datetime.context_timestamp(task, task.date_deadline).strftime('%d.%m.%Y')                 if task.date_deadline else ''
