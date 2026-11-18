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
            node['can_check'] = (node['status'] != 'cancelled'
                                 and not res.get('readonly') and task._sh_can_check(self))
            # marked "შესრულებულია" by the assignee, waits for the reviewer
            node['in_review'] = task.stage_id.sh_kind == 'review' and task.state not in CLOSED
            prev = task._sh_all_previous()
            node['prev_total'] = len(prev)
            node['prev_done'] = len(prev.filtered(lambda t: t.state in CLOSED))
            # a step still waiting for previous ones cannot be ticked (switching off stays possible)
            if node['can_check'] and node['prev_done'] < node['prev_total']                     and not node['in_review'] and task.state not in CLOSED:
                node['can_check'] = False
        return self._sh_chain_hide_cancelled(res)

    @staticmethod
    def _sh_chain_hide_cancelled(res):
        """Cancelled steps disappear from the sequence (the opened task always stays);
        their previous and next steps are joined, the columns close up."""
        nodes = res.get('nodes', [])
        gone = {n['id'] for n in nodes if n['status'] == 'cancelled' and not n['current']}
        if not gone:
            return res
        edges = res.get('edges', [])
        done = {n['id']: n['status'] == 'done' for n in nodes}
        prev_of, next_of = {}, {}
        for a, b, _ok in edges:
            next_of.setdefault(a, set()).add(b)
            prev_of.setdefault(b, set()).add(a)

        def live(start, links):
            out, todo, seen = set(), list(links.get(start, ())), set()
            while todo:
                x = todo.pop()
                if x in seen:
                    continue
                seen.add(x)
                if x in gone:
                    todo.extend(links.get(x, ()))
                else:
                    out.add(x)
            return out

        new_edges = {(a, b) for a, b, _ok in edges if a not in gone and b not in gone}
        for g in gone:
            for a in live(g, prev_of):
                for b in live(g, next_of):
                    new_edges.add((a, b))
        kept = [n for n in nodes if n['id'] not in gone]
        levels = sorted({n['level'] for n in kept})
        for n in kept:
            n['level'] = levels.index(n['level'])
        res['nodes'] = kept
        res['edges'] = [[a, b, done.get(a, False)] for a, b in sorted(new_edges)]
        res['prev'] = [i for i in res.get('prev', []) if i not in gone]
        res['next'] = [i for i in res.get('next', []) if i not in gone]
        return res

    def sh_chain_toggle_done(self, task_id):
        """The switch on a step card marks the step as performed ("შესრულებულია") from the assignee's
        side: it goes to "შემოწმებაზე" and its reviewers confirm or reject it in the
        "დადასტურებები" app. Switched off (performed or already confirmed) - back in progress."""
        task = self._sh_chain_member(task_id)
        user = self.env.user
        if not task.with_user(user)._sh_can_check(self):
            raise UserError(_("ამ ნაბიჯის მონიშვნა შეუძლია მის შემსრულებელს, მთავარ პასუხისმგებელს ან ადმინისტრატორს."))
        prev, subs = task._sh_open_before_review()
        if task.state == '1_done' or task.stage_id.sh_kind == 'review':
            kind, icon, note = 'in_progress', '↺', _("თანმიმდევრობიდან ისევ გაიხსნა")
        else:
            # same rule as the form / stage bar: not to review while a previous step or sub-task is open
            if prev or subs:
                lines = ['თანმიმდევრობა: %s' % self._sh_label(t) for t in prev.sorted('id')]
                lines += ['ქვედავალება: %s' % t.name for t in subs.sorted('id')]
                raise UserError(_("შემოწმებაზე გადაყვანა ჯერ არ შეიძლება - დასასრულებელია:\n%s")
                                % '\n'.join('• ' + line for line in lines))
            kind, icon = 'review', '🔎'
            note = _("თანმიმდევრობიდან მოინიშნა შესრულებულად - გადავიდა შემოწმებაზე (%s)",
                     ', '.join((task.reviewer_ids or task.create_uid).mapped('name')))
        stage = task._sh_stage_of_kind(kind)
        if not stage:
            raise UserError(_("ამ დეპარტამენტს არ აქვს შესაბამისი სტადია."))
        # reopened while a previous step is still open: it keeps waiting
        state = '04_waiting_normal' if kind == 'in_progress' and prev else '01_in_progress'
        task.with_context(sh_flow_internal=True, sh_final_given=True).write(
            {'stage_id': stage.id, 'state': state})
        task.message_post(
            body=Markup('%s <b>%s</b>') % (icon, note),
            author_id=user.partner_id.id, message_type='notification', subtype_xmlid='mail.mt_note')
        return True
