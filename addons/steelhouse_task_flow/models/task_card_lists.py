"""Boards show only the main tasks: sequence steps (tasks with a next task) are hidden by the default
filter "მხოლოდ მთავარი დავალებები"; the card lists its sub-tasks and steps on demand
(static/src/card_lists)."""
from odoo import api, fields, models

CLOSED = ('1_done', '1_canceled')
STATE_LABEL = {'1_done': '✔ დასრულდა', '1_canceled': 'გაუქმდა', '04_waiting_normal': '🔒 ელოდება'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_is_step = fields.Boolean('თანმიმდევრობის ნაბიჯი', compute='_compute_sh_is_step', store=True, index=True,
                                help="დავალებას აქვს შემდეგი დავალება თანმიმდევრობაში.")
    sh_step_total = fields.Integer(compute='_compute_sh_step_counts')
    sh_step_done = fields.Integer(compute='_compute_sh_step_counts')

    @api.depends('dependent_ids')
    def _compute_sh_is_step(self):
        for task in self:
            task.sh_is_step = bool(task.dependent_ids)

    def _compute_sh_step_counts(self):
        for task in self:
            prev = task._sh_all_previous() if task.id else self.browse()
            task.sh_step_total = len(prev)
            task.sh_step_done = len(prev.filtered(lambda t: t.state in CLOSED))

    def sh_card_list(self, kind):
        """Items for the card: 'subtasks' or 'steps' (in order)."""
        self.ensure_one()
        me = self.sudo()
        if kind == 'steps':
            tasks = me._sh_all_previous()
            level = self._sh_layers(tasks | me)
            tasks = tasks.sorted(lambda t: (level.get(t.id, 0), t.sequence, t.id))
        else:
            tasks = me.child_ids.sorted(lambda t: (t.sequence, t.id))
        return [{
            'id': t.id,
            'name': t.name,
            'number': t.sh_number or '',
            'done': t.state in CLOSED,
            'label': STATE_LABEL.get(t.state, ''),
        } for t in tasks if t.state != '1_canceled']
