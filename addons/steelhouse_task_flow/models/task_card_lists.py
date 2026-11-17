"""Boards show only the main tasks: sequence steps (tasks with a next task) are hidden by the default
filter "მხოლოდ მთავარი დავალებები"; the card lists its sub-tasks and steps on demand
(static/src/card_lists)."""
from odoo import api, fields, models
from odoo.fields import Domain

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

    # ------------------------------------------------------------------ steps off every board / list
    def _sh_hide_steps(self, domain):
        """Sequence steps are seen only inside their main task's card: every board, list and
        grouped view of tasks drops them - wherever it is opened from. Kept when the domain
        asks for specific tasks (ids, e.g. "open these tasks" lists) or for steps explicitly,
        or with the context key sh_show_steps."""
        if self.env.context.get('sh_show_steps'):
            return domain
        text = str(domain or '')
        if "'sh_is_step'" in text or "'id'" in text or "'parent_id'" in text:
            return domain
        return Domain.AND([Domain(domain or []), Domain('sh_is_step', '=', False)])

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(self._sh_hide_steps(domain), specification, offset=offset, limit=limit,
                                       order=order, count_limit=count_limit)

    @api.model
    def web_read_group(self, domain, groupby, aggregates=(), limit=None, offset=0, order=None, **kwargs):
        return super().web_read_group(self._sh_hide_steps(domain), groupby, aggregates=aggregates, limit=limit,
                                      offset=offset, order=order, **kwargs)

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
