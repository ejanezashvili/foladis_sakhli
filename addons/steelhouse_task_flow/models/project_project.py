from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sh_is_department = fields.Boolean(
        string='დეპარტამენტი', default=False, index=True,
        help="დეპარტამენტის პროექტი (ჩანს „დეპარტამენტებში“). "
             "მოხსნილი — კონკრეტული პროექტი (ჩანს „პროექტებში“).")
    sh_task_ids = fields.One2many('project.task', 'sh_project_id', string='პროექტის დავალებები')

    # A concrete project counts the tasks linked to it by "პროექტი" (sh_project_id);
    # departments keep Odoo's counts (tasks whose project_id is the department).
    def _sh_count(self, field, domain):
        projects = self.filtered(lambda p: not p.sh_is_department and p.id)
        if not projects:
            return
        Task = self.env['project.task'].with_context(active_test=any(p.active for p in projects))
        counts = dict(Task._read_group([('sh_project_id', 'in', projects.ids)] + domain, ['sh_project_id'], ['__count']))
        for project in projects:
            project[field] = counts.get(project, 0)

    def _compute_task_count(self):
        super()._compute_task_count()
        self._sh_count('task_count', [])

    def _compute_open_task_count(self):
        super()._compute_open_task_count()
        self._sh_count('open_task_count', [('state', 'in', self.env['project.task'].OPEN_STATES)])

    def _compute_closed_task_count(self):
        super()._compute_closed_task_count()
        self._sh_count('closed_task_count', [('state', 'not in', self.env['project.task'].OPEN_STATES)])

    def action_view_tasks(self):
        """Concrete project: its tasks are the ones whose "პროექტი" is this project;
        each task keeps the flow (stages) of its department (project_id)."""
        action = super().action_view_tasks()
        if self.sh_is_department:
            return action
        ctx = dict(action['context'])
        ctx.pop('default_project_id', None)
        ctx.update({'default_sh_project_id': self.id, 'sh_project_view': self.id})
        action['context'] = ctx
        action['domain'] = [('sh_project_id', '=', self.id)]
        return action
