"""„თანმიმდევრობა“ (task chain): tasks linked one after another across departments.

Built on Odoo's own dependencies (depend_on_ids / dependent_ids): a task whose previous
tasks are not finished is "waiting" (04_waiting_normal) and cannot be accepted or moved on;
when the last previous task is finished, the next task's people are notified.
Data for the widget is in static/src/task_chain.
"""
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

CLOSED = ('1_done', '1_canceled')
# stage kinds a waiting task may not enter
LOCKED_KINDS = ('accepted', 'in_progress', 'review', 'done')
MAX_NODES = 80


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_chain = fields.Char(compute='_compute_sh_chain', string='თანმიმდევრობა')
    sh_waiting_for = fields.Char(compute='_compute_sh_waiting_for', string='ელოდება')

    def _compute_sh_chain(self):
        for task in self:
            task.sh_chain = ''

    @api.depends('depend_on_ids.state', 'depend_on_ids.name')
    def _compute_sh_waiting_for(self):
        for task in self:
            open_prev = task.sudo().depend_on_ids.filtered(lambda t: t.state not in CLOSED)
            task.sh_waiting_for = ', '.join(
                '%s%s' % (t.sh_number and t.sh_number + ' ' or '', t.name) for t in open_prev)

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def _sh_open_previous(self):
        self.ensure_one()
        return self.sudo().depend_on_ids.filtered(lambda t: t.state not in CLOSED)

    def _sh_check_not_waiting(self, kind):
        for task in self.filtered(lambda t: not t.is_template):
            prev = task._sh_open_previous()
            if prev:
                raise UserError(_(
                    "„%(task)s“ ჯერ ვერ გადავა შემდეგ ეტაპზე — ელოდება წინა დავალებებს:\n%(prev)s",
                    task=task.name,
                    prev='\n'.join('• %s%s (%s)' % (t.sh_number and t.sh_number + ' ' or '', t.name,
                                                    t.project_id.name or '—') for t in prev)))

    def write(self, vals):
        if vals.get('stage_id') and not self.env.context.get('sh_flow_internal') and not self.env.su:
            kind = self.env['project.task.type'].browse(vals['stage_id']).sh_kind
            if kind in LOCKED_KINDS:
                self.filtered(lambda t: t.stage_id.id != vals['stage_id'])._sh_check_not_waiting(kind)
        watch = 'state' in vals or 'stage_id' in vals or 'depend_on_ids' in vals
        before = {}
        if watch:
            nexts = self.sudo().dependent_ids
            before = {t.id: t.state for t in nexts}
        res = super().write(vals)
        if watch and before:
            self.sudo().dependent_ids.filtered(
                lambda t: before.get(t.id) == '04_waiting_normal' and t.state not in ('04_waiting_normal',) + CLOSED
            )._sh_notify_unlocked()
        return res

    def _sh_notify_unlocked(self):
        """All previous tasks are finished: tell the next task's people they can start."""
        for task in self:
            partners = (task.user_ids | task.sh_responsible_id).partner_id
            prev = task.depend_on_ids
            body = Markup("🔓 <b>%s</b><br/>%s") % (
                _("წინა დავალებები შესრულდა — შეგიძლიათ დაიწყოთ."),
                ', '.join('%s%s' % (t.sh_number and t.sh_number + ' ' or '', t.name) for t in prev))
            task.message_post(body=body, message_type='notification', subtype_xmlid='mail.mt_note',
                              partner_ids=partners.ids)

    # ------------------------------------------------------------------
    # Data for the widget
    # ------------------------------------------------------------------
    def _sh_chain_tasks(self):
        """The connected group of tasks (previous and next, any depth), as superuser."""
        self.ensure_one()
        seen = self.sudo()
        todo = self.sudo()
        while todo and len(seen) < MAX_NODES:
            around = (todo.depend_on_ids | todo.dependent_ids) - seen
            seen |= around
            todo = around
        return seen

    @staticmethod
    def _sh_layers(tasks):
        """Column of each task: the longest path of previous tasks before it."""
        ids = set(tasks.ids)
        level = {}

        def depth(task, stack=()):
            if task.id in level:
                return level[task.id]
            if task.id in stack:  # safety, Odoo forbids cycles
                return 0
            prev = [p for p in task.depend_on_ids if p.id in ids]
            level[task.id] = max((depth(p, stack + (task.id,)) + 1 for p in prev), default=0)
            return level[task.id]

        for task in tasks:
            depth(task)
        return level

    def _sh_node_status(self):
        self.ensure_one()
        if self.state == '1_done':
            return 'done'
        if self.state == '1_canceled':
            return 'cancelled'
        if self.state == '04_waiting_normal' or self._sh_open_previous():
            return 'waiting'
        return 'active'

    def sh_chain_data(self):
        self.ensure_one()
        if not self.id:
            return {'nodes': [], 'edges': [], 'readonly': True}
        tasks = self._sh_chain_tasks()
        level = self._sh_layers(tasks)
        readable = set(self.env['project.task'].search([('id', 'in', tasks.ids)]).ids)
        nodes = []
        for t in tasks:
            deadline = t.date_deadline and fields.Datetime.context_timestamp(self, t.date_deadline)
            user = t.sh_responsible_id or t.user_ids[:1]
            nodes.append({
                'id': t.id,
                'number': t.sh_number or '',
                'name': t.name,
                'department': t.project_id.name or '',
                'user_id': user.id or False,
                'user_name': user.name or '',
                'deadline': deadline and deadline.strftime('%d.%m.%Y') or '',
                'overdue': bool(deadline and t.state not in CLOSED and t.date_deadline < fields.Datetime.now()),
                'stage': t.stage_id.name or '',
                'status': t._sh_node_status(),
                'level': level.get(t.id, 0),
                'current': t.id == self.id,
                'can_open': t.id in readable,
                'progress': t.sh_progress,
            })
        nodes.sort(key=lambda n: (n['level'], not n['current'], n['id']))
        ids = set(tasks.ids)
        edges = [[p.id, t.id, p.state == '1_done'] for t in tasks for p in t.depend_on_ids if p.id in ids]
        me = self.sudo()
        return {
            'nodes': nodes,
            'edges': edges,
            'prev': me.depend_on_ids.ids,
            'next': me.dependent_ids.ids,
            'readonly': not self.has_access('write'),
            'project': me.sh_project_id.name or '',
            'truncated': len(tasks) >= MAX_NODES,
        }

    @api.model
    def sh_chain_departments(self):
        projects = self.env['project.project'].sudo().search(
            [('sh_is_department', '=', True), ('is_template', '=', False)], order='name')
        return [{'id': p.id, 'name': p.name} for p in projects]

    @api.model
    def sh_chain_users(self, project_id):
        """Users of the department first (members of the HR department and its sub-departments,
        heads included), then everyone else."""
        Users = self.env['res.users'].sudo()
        everyone = Users.search([('share', '=', False)], order='name')
        dept = self.env['project.project'].sudo().browse(project_id).sh_department_id if project_id else False
        mine = Users
        if dept:
            employees = self.env['hr.employee'].sudo().search([('department_id', 'child_of', dept.id)])
            mine = (employees.user_id | dept.sh_all_manager_user_ids).filtered(lambda u: not u.share)
            mine = mine.sorted('name')
        return {
            'department': [{'id': u.id, 'name': u.name} for u in mine],
            'others': [{'id': u.id, 'name': u.name} for u in everyone - mine],
        }

    def sh_chain_search(self, term):
        """Existing tasks that can be linked (not already in this chain)."""
        self.ensure_one()
        chain = self._sh_chain_tasks()
        domain = [('is_template', '=', False), ('parent_id', '=', False), ('project_id', '!=', False), ('id', 'not in', chain.ids),
                  ('state', 'not in', list(CLOSED))]
        if term:
            domain += ['|', ('name', 'ilike', term), ('sh_number', 'ilike', term)]
        found = self.env['project.task'].search(domain, limit=12, order='id desc')
        return [{'id': t.id, 'label': '%s%s' % (t.sh_number and t.sh_number + ' · ' or '', t.name),
                 'department': t.project_id.name or ''} for t in found]

    # ------------------------------------------------------------------
    # Changes from the widget
    # ------------------------------------------------------------------
    def _sh_chain_check_rights(self):
        self.ensure_one()
        self.check_access('write')

    @staticmethod
    def _sh_label(task):
        return '%s%s' % (task.sh_number and task.sh_number + ' ' or '', task.name)

    def _sh_chain_log(self, direction, other):
        """Note on both tasks, each from its own side."""
        names = {'next': _("შემდეგი დავალება"), 'prev': _("წინა დავალება")}
        opposite = 'prev' if direction == 'next' else 'next'
        for task, text, label in ((self, names[direction], self._sh_label(other)),
                                  (other, names[opposite], self._sh_label(self))):
            task.sudo().message_post(body=Markup("⛓ %s: <b>%s</b>") % (text, label),
                                     message_type='notification', subtype_xmlid='mail.mt_note')

    def _sh_chain_connect(self, direction, other):
        """direction 'next': other starts after self; 'prev': self starts after other."""
        me = self.sudo()
        other = other.sudo()
        if direction == 'next':
            other.write({'depend_on_ids': [(4, me.id)]})
        else:
            me.write({'depend_on_ids': [(4, other.id)]})
        self._sh_chain_log(direction, other)

    def _sh_anchor(self, anchor_id):
        """The chain task a new step is added before/after (this task by default).
        Rights: the user must be able to edit the task the tab is opened on."""
        self._sh_chain_check_rights()
        if not anchor_id or anchor_id == self.id:
            return self
        anchor = self._sh_chain_tasks().filtered(lambda t: t.id == anchor_id)
        if not anchor:
            raise UserError(_("დავალება ამ თანმიმდევრობაში ვერ მოიძებნა."))
        return anchor

    def sh_chain_link(self, direction, task_id, anchor_id=False):
        anchor = self._sh_anchor(anchor_id)
        other = self.env['project.task'].browse(task_id).exists()
        if not other or other == anchor:
            raise UserError(_("დავალება ვერ მოიძებნა."))
        anchor._sh_chain_connect(direction, other)
        return True

    def sh_chain_unlink_edge(self, prev_id, next_id):
        """Remove one arrow of the chain (prev_id -> next_id)."""
        self._sh_chain_check_rights()
        chain = self._sh_chain_tasks()
        prev = chain.filtered(lambda t: t.id == prev_id)
        nxt = chain.filtered(lambda t: t.id == next_id)
        if not prev or not nxt:
            raise UserError(_("კავშირი ვერ მოიძებნა."))
        nxt.write({'depend_on_ids': [(3, prev.id)]})
        for task, other in ((prev, nxt), (nxt, prev)):
            task.message_post(body=Markup("⛓ %s: <b>%s</b>") % (_("კავშირი მოიხსნა"), self._sh_label(other)),
                              message_type='notification', subtype_xmlid='mail.mt_note')
        return True

    def sh_chain_unlink(self, direction, task_id):
        self._sh_chain_check_rights()
        me = self.sudo()
        other = self.env['project.task'].sudo().browse(task_id)
        if direction == 'next':
            other.write({'depend_on_ids': [(3, me.id)]})
        else:
            me.write({'depend_on_ids': [(3, other.id)]})
        for task in (me | other):
            task.message_post(body=Markup("⛓ %s: <b>%s</b>") % (
                _("კავშირი მოიხსნა"), (other if task == me else me).name),
                message_type='notification', subtype_xmlid='mail.mt_note')
        return True

    def _sh_end_of_day(self, day):
        """'2026-11-20' -> 20.11 23:59 in the user's time zone, stored in UTC."""
        if not day:
            return False
        import pytz
        from datetime import datetime, time
        tz = pytz.timezone(self.env.user.tz or 'Asia/Tbilisi')
        local = tz.localize(datetime.combine(fields.Date.to_date(day), time(23, 59)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def sh_chain_create(self, direction, vals, anchor_id=False):
        """New task before/after this one (or another task of the chain), in any department,
        with its responsible person, reviewers, deadline and sub-tasks."""
        anchor = self._sh_anchor(anchor_id)
        name = (vals.get('name') or '').strip()
        if not name:
            raise UserError(_("ჩაწერეთ დავალების სახელი."))
        project = self.env['project.project'].sudo().browse(vals.get('project_id') or 0).exists()
        if not project:
            raise UserError(_("აირჩიეთ დეპარტამენტი."))
        user_id = vals.get('user_id') or False
        create_vals = {
            'name': name,
            'project_id': project.id,
            'sh_project_id': self.sh_project_id.id,
            'user_ids': [(6, 0, [user_id] if user_id else [])],
            'sh_responsible_id': user_id,
            'date_deadline': self._sh_end_of_day(vals.get('deadline')),
            'reviewer_ids': [(6, 0, [int(r) for r in (vals.get('reviewer_ids') or []) if r] or [self.env.user.id])],
        }
        if vals.get('description'):
            create_vals['description'] = vals['description']
        first = project.type_ids.filtered(lambda s: s.sh_kind == 'new')[:1]
        if first:
            create_vals['stage_id'] = first.id
        # sudo: the next task may be in a department the creator does not see;
        # the creator stays create_uid, so they keep access to it (rule "create_uid")
        new = self.env['project.task'].sudo().with_context(default_project_id=project.id).create(create_vals)
        subs = [s for s in (vals.get('subtasks') or []) if (s.get('name') or '').strip()]
        if subs:
            section = self.env['steelhouse.task.section'].sudo().create({'task_id': new.id, 'name': '', 'sequence': 10})
            for s in subs:
                sub_id = new.sh_steps_add_item(section.id)
                new.sh_steps_write_item(sub_id, {
                    'name': s['name'], 'user_id': s.get('user_id') or False, 'deadline': s.get('deadline') or False})
        anchor._sh_chain_connect(direction, new)
        return new.id
