"""Stage bar on the task form: done / returned / cancelled are shown only to those who may use
them (the reviewers or a system administrator - same rule as `_sh_check_reviewer`). The assignee
sends the task to review with "✔ შესრულებულია"; the current stage always stays visible."""
from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_can_close = fields.Boolean(compute='_compute_sh_can_close')

    @api.depends_context('uid')
    @api.depends('reviewer_ids')
    def _compute_sh_can_close(self):
        for task in self:
            task.sh_can_close = task._sh_can_review()
