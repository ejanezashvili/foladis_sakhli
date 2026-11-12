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
