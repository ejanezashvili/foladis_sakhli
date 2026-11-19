"""„თანმიმდევრობა“ tab: the main task is not a step.

The main task (the end of the sequence) is taken out of the steps of the widget and shown in a
strip above them ("მთავარი დავალება: ... · ნაბიჯები: x / y"). A new step is inserted between
two tasks ("between": after the anchor, before the anchor's next tasks), so "+ ნაბიჯის დამატება"
adds the last step before the main task instead of a branch after it.
"""
from odoo import api, models

CLOSED = ('1_done', '1_canceled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_chain_main(self):
        """The main task of this sequence: follow the next tasks to the end."""
        self.ensure_one()
        main, seen = self.sudo(), self.browse()
        while main.dependent_ids and main not in seen:
            seen |= main
            main = main.dependent_ids.sorted('id')[:1]
        return main

    def sh_chain_data(self):
        res = super().sh_chain_data()
        if not self.id or not res.get('nodes'):
            return res
        main = self._sh_chain_main()
        steps = main._sh_all_previous().filtered(lambda t: t.state != '1_canceled')
        readable = bool(self.env['project.task'].search_count([('id', '=', main.id)]))
        res['main'] = {
            'id': main.id,
            'number': main.sh_number or '',
            'name': main.name,
            'current': main.id == self.id,
            'can_open': readable,
            'status': main._sh_node_status(),
            'stage': main.stage_id.name or '',
            'level': 0,
            'prev_total': len(steps),
            'prev_done': len(steps.filtered(lambda t: t.state in CLOSED)),
        }
        res['nodes'] = [n for n in res['nodes'] if n['id'] != main.id]
        res['edges'] = [e for e in res['edges'] if main.id not in (e[0], e[1])]
        # levels start at 0 again without the main task
        if res['nodes']:
            low = min(n['level'] for n in res['nodes'])
            for n in res['nodes']:
                n['level'] -= low
        return res

    def _sh_chain_connect(self, direction, other):
        """'between': other goes right after self, and the tasks that followed self now follow other."""
        if direction != 'between':
            return super()._sh_chain_connect(direction, other)
        nexts = self.sudo().dependent_ids - other.sudo()
        super()._sh_chain_connect('next', other)
        for nxt in nexts:
            nxt.sudo().write({'depend_on_ids': [(3, self.id), (4, other.id)]})

    # ------------------------------------------------------------------ the main task is never "waiting"
    # It is the whole job; its steps are its parts. It can be accepted and worked on at any time;
    # "შემოწმებაზე" / "დასრულებული" still wait for all its steps (_sh_check_not_waiting,
    # _sh_open_before_review). Steps keep waiting for each other.
    def _sh_is_main(self):
        return bool(not self.sh_is_step and self.depend_on_ids and not self.is_template)

    def is_blocked_by_dependences(self):
        if self._sh_is_main():
            return False
        return super().is_blocked_by_dependences()

    @api.depends('dependent_ids')
    def _compute_state(self):
        super()._compute_state()
        for task in self.filtered(lambda t: t.state == '04_waiting_normal' and t._sh_is_main()):
            task.state = '01_in_progress'

    def _sh_check_not_waiting(self, kind):
        if kind in ('accepted', 'in_progress'):
            self = self.filtered(lambda t: not t._sh_is_main())
        return super()._sh_check_not_waiting(kind)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == '04_waiting_normal' or 'depend_on_ids' in vals or 'dependent_ids' in vals:
            mains = self.sudo().filtered(lambda t: t.state == '04_waiting_normal' and t._sh_is_main())
            if mains:
                mains.with_context(sh_flow_internal=True).write({'state': '01_in_progress'})
        return res
