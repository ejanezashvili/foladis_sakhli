"""Sequence steps can be ticked done right on their card (same switch as sub-tasks), and a task
cannot go to "შემოწმებაზე" while one of its previous steps or sub-tasks is still open."""
from markupsafe import Markup

from odoo import _, models
from odoo.exceptions import UserError

CLOSED = ('1_done', '1_canceled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_all_previous(self):
        """Every task before this one in its sequence (any depth), as superuser."""
        self.ensure_one()
        seen = self.browse()
        todo = self.sudo().depend_on_ids
        while todo:
            seen |= todo
            todo = todo.depend_on_ids - seen
        return seen

    def _sh_open_before_review(self):
        self.ensure_one()
        prev = self._sh_all_previous().filtered(lambda t: t.state not in CLOSED)
        subs = self.sudo().child_ids.filtered(lambda t: t.state not in CLOSED)
        return prev, subs

    def write(self, vals):
        if vals.get('stage_id') and not self.env.context.get('sh_flow_internal'):
            kind = self.env['project.task.type'].browse(vals['stage_id']).sh_kind
            if kind == 'review':
                for task in self.filtered(lambda t: t.stage_id.sh_kind != 'review'):
                    prev, subs = task._sh_open_before_review()
                    if prev or subs:
                        lines = ['თანმიმდევრობა: %s' % self._sh_label(t) for t in prev.sorted('id')]
                        lines += ['ქვედავალება: %s' % t.name for t in subs.sorted('id')]
                        raise UserError(_("შემოწმებაზე გადაყვანა ჯერ არ შეიძლება - დასასრულებელია:\n%s")
                                        % '\n'.join('• ' + line for line in lines))
        return super().write(vals)

    # ------------------------------------------------------------------ sequence cards
    def _sh_can_check(self, opened):
        """Who may tick a step: its assignee / main responsible, the main responsible of the
        task the tab is opened on, or a project administrator."""
        user = self.env.user
        return (user.has_group('project.group_project_manager') or user in self.user_ids
                or user == self.sh_responsible_id or user == opened.sudo().sh_responsible_id)

    def sh_chain_data(self):
        res = super().sh_chain_data()
        Task = self.env['project.task'].sudo()
        for node in res.get('nodes', []):
            task = Task.browse(node['id'])
            node['can_check'] = (not node['current'] and node['status'] != 'cancelled'
                                 and not res.get('readonly') and task._sh_can_check(self))
            prev = task._sh_all_previous()
            node['prev_total'] = len(prev)
            node['prev_done'] = len(prev.filtered(lambda t: t.state in CLOSED))
        return res

    def sh_chain_toggle_done(self, task_id):
        """The switch on a step card: done <-> back in progress (no reviewer step)."""
        task = self._sh_chain_member(task_id)
        if task.id == self.id or not task.with_user(self.env.user)._sh_can_check(self):
            raise UserError(_("ამ ნაბიჯის მონიშვნა შეუძლია მის შემსრულებელს, მთავარ პასუხისმგებელს ან ადმინისტრატორს."))
        done = task.state != '1_done'
        stage = task._sh_stage_of_kind('done' if done else 'in_progress')
        if not stage:
            raise UserError(_("ამ დეპარტამენტს არ აქვს შესაბამისი სტადია."))
        task.with_context(sh_flow_internal=True, sh_final_given=True).write({
            'stage_id': stage.id, 'state': '1_done' if done else '01_in_progress'})
        task.message_post(
            body=Markup('%s <b>%s</b>') % ('✔' if done else '↺', _("თანმიმდევრობიდან მოინიშნა დასრულებულად")
                                           if done else _("თანმიმდევრობიდან ისევ გაიხსნა")),
            author_id=self.env.user.partner_id.id, message_type='notification', subtype_xmlid='mail.mt_note')
        return True
