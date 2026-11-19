"""An employee's sequence step card: the main task on top, the stage, and the whole sequence
(drop-down, the employee's own steps in blue). Admins never see step cards (task_card_lists)."""
from odoo import api, fields, models

CLOSED = ('1_done', '1_canceled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_step_main_label = fields.Char(compute='_compute_sh_step_chain')
    sh_step_chain_total = fields.Integer(compute='_compute_sh_step_chain')
    sh_step_chain_done = fields.Integer(compute='_compute_sh_step_chain')

    def _sh_chain_steps_sorted(self, main):
        steps = main._sh_all_previous().filtered(lambda t: t.state != '1_canceled')
        level = self._sh_layers(steps | main)
        return steps.sorted(lambda t: (level.get(t.id, 0), t.sequence, t.id))

    @api.depends('sh_is_step')
    def _compute_sh_step_chain(self):
        for task in self:
            task.sh_step_main_label = False
            task.sh_step_chain_total = task.sh_step_chain_done = 0
            if not task.id or not task.sh_is_step:
                continue
            main = task._sh_chain_main()
            steps = main._sh_all_previous().filtered(lambda t: t.state != '1_canceled')
            task.sh_step_main_label = '%s%s' % (main.sh_number and main.sh_number + ' ' or '', main.name)
            task.sh_step_chain_total = len(steps)
            task.sh_step_chain_done = len(steps.filtered(lambda t: t.state in CLOSED))

    def sh_card_list(self, kind):
        """'chain' (on a step card): all steps of its main task; on every list the user's own
        tasks are marked as mine (blue, bold)."""
        if kind != 'chain':
            items = super().sh_card_list(kind)
            mine = set(self.env['project.task'].sudo().search(
                [('id', 'in', [i['id'] for i in items]), ('user_ids', 'in', self.env.uid)]).ids)
            for item in items:
                item['mine'] = item['id'] in mine
            return items
        self.ensure_one()
        main = self._sh_chain_main()
        uid = self.env.uid
        return [{
            'id': t.id,
            'name': t.name,
            'number': t.sh_number or '',
            'done': t.state in CLOSED,
            'label': self._sh_card_stage(t)[1],
            'kind': self._sh_card_stage(t)[0],
            'mine': uid in t.user_ids.ids,
        } for t in self._sh_chain_steps_sorted(main)]
