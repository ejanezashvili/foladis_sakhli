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

    # ------------------------------------------------------------------ badge on a step card
    # wait - a previous step is still open; turn - the previous ones are closed, the step can be worked on
    sh_step_badge = fields.Selection([('wait', 'ელოდება წინა ნაბიჯს'), ('turn', 'შენი ჯერია')],
                                     compute='_compute_sh_step_badge')
    sh_step_pos = fields.Char(compute='_compute_sh_step_badge')
    sh_step_info = fields.Text(compute='_compute_sh_step_badge')

    def _compute_sh_step_badge(self):
        for task in self:
            task.sh_step_badge = task.sh_step_pos = task.sh_step_info = False
            if not task.id or not task.sh_is_step:
                continue
            me = task.sudo()
            # the main task: the end of the sequence
            main, seen = me, me.browse()
            while main.dependent_ids and main not in seen:
                seen |= main
                main = main.dependent_ids[:1]
            steps = main._sh_all_previous().filtered(lambda t: t.state != '1_canceled')
            level = self._sh_layers(steps | main)
            steps = steps.sorted(lambda t: (level.get(t.id, 0), t.sequence, t.id))
            num = {t.id: i + 1 for i, t in enumerate(steps)}
            if me.id not in num:
                continue
            task.sh_step_pos = '%d/%d' % (num[me.id], len(steps))

            def who(t):
                return ', '.join(t.user_ids.mapped('name')) or '-'

            open_prev = me._sh_all_previous().filtered(lambda t: t.state not in CLOSED)
            if task.state in CLOSED:
                continue
            lines = []
            if open_prev:
                task.sh_step_badge = 'wait'
                for t in open_prev.sorted(lambda t: num.get(t.id, 0)):
                    lines.append('წინა: %s. %s - %s (%s)' % (num.get(t.id, '?'), t.name, who(t), t.stage_id.name or ''))
                lines.append('მთავარი დავალება: „%s“%s' % (main.name, main.sh_number and ' (%s)' % main.sh_number or ''))
            else:
                task.sh_step_badge = 'turn'
                if me.depend_on_ids:
                    lines.append('წინა ნაბიჯი დასრულდა')
                for t in me.dependent_ids.filtered(lambda t: t.state != '1_canceled'):
                    if t == main:
                        lines.append('შემდეგი: მთავარი დავალება „%s“ - %s' % (t.name, who(t)))
                    else:
                        lines.append('შემდეგი: %s. %s - %s' % (num.get(t.id, '?'), t.name, who(t)))
            task.sh_step_info = chr(10).join(lines)

    # ------------------------------------------------------------------ steps off every board / list
    def _sh_hide_steps(self, domain):
        """Sequence steps are seen only inside their main task's card: every board, list and
        grouped view of tasks drops them - wherever it is opened from (an employee still sees the
        steps he performs). Kept when the domain
        asks for specific tasks (ids, e.g. "open these tasks" lists) or for steps explicitly,
        or with the context key sh_show_steps."""
        if self.env.context.get('sh_show_steps'):
            return domain
        text = str(domain or '')
        if "'sh_is_step'" in text or "'id'" in text or "'parent_id'" in text:
            return domain
        hide = Domain('sh_is_step', '=', False)
        # employees see their own steps as cards (with the step badge); project administrators don't
        if not self.env.user.has_group('project.group_project_manager'):
            hide = hide | Domain('user_ids', 'in', [self.env.uid])
        return Domain.AND([Domain(domain or []), hide])

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
