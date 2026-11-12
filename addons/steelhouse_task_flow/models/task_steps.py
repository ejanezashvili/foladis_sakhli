from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TaskSection(models.Model):
    """A stage of work inside a task ("აზომვა", "დიზაინი"...); groups its sub-tasks."""
    _name = 'steelhouse.task.section'
    _description = 'დავალების ეტაპი (ქვედავალებების ჯგუფი)'
    _order = 'sequence, id'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade', index=True)
    name = fields.Char('ეტაპი', default='')
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', 'პასუხისმგებელი', domain="[('share', '=', False)]")
    date_deadline = fields.Date('ვადა')
    done_date = fields.Datetime('დასრულდა', help="როცა ეტაპის ყველა ქვედავალება შესრულდა.")

    def _sh_update_done(self):
        for section in self:
            items = section.subtask_ids.filtered(lambda t: t.state != '1_canceled')
            all_done = items and all(t.state == '1_done' for t in items)
            if all_done and not section.done_date:
                section.done_date = fields.Datetime.now()
            elif not all_done and section.done_date:
                section.done_date = False
    subtask_ids = fields.One2many('project.task', 'sh_section_id', string='ქვედავალებები')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_section_id = fields.Many2one('steelhouse.task.section', string='ეტაპი', index=True,
                                    ondelete='set null', copy=False)
    sh_section_ids = fields.One2many('steelhouse.task.section', 'task_id', string='ეტაპები')
    sh_steps = fields.Char(compute='_compute_sh_steps', string='ქვედავალებები')

    def copy(self, default=None):
        """Copies (templates, tasks from templates, repeats) keep the stages and sub-tasks
        exactly; only dates and "done" marks are reset."""
        olds = list(self)
        news = super().copy(default)
        for old, new in zip(olds, news):
            old._sh_copy_steps_to(new)
        return news

    def _sh_copy_steps_to(self, new):
        if not self.sh_section_ids and not self.child_ids:
            return
        Section = self.env['steelhouse.task.section']
        mapping = {}
        for section in self.sh_section_ids:
            mapping[section.id] = Section.create({
                'task_id': new.id, 'name': section.name, 'sequence': section.sequence,
                'user_id': section.user_id.id,
            }).id
        old_children = self.with_context(active_test=False).child_ids.sorted(lambda t: (t.sequence, t.id))
        new_children = new.with_context(active_test=False).child_ids.sorted(lambda t: (t.sequence, t.id))
        used = set()
        for nc in new_children:
            match = next((oc for oc in old_children if oc.id not in used
                          and nc.name in (oc.name, _('%s (copy)', oc.name), oc.name + ' (ასლი)')), None)
            if not match:
                continue
            used.add(match.id)
            nc.with_context(sh_flow_internal=True, mail_notrack=True).write({
                'name': match.name,
                'sh_section_id': mapping.get(match.sh_section_id.id, False),
                'user_ids': [(6, 0, match.user_ids.ids)],
                'date_deadline': False,
                'state': '01_in_progress',
                'sh_done_user_id': False,
                'sh_done_date': False,
            })

    def _sh_checklist_to_steps(self):
        """Checklist in the description -> sub-tasks in a stage (used when saving a template)."""
        import re
        from markupsafe import Markup
        for task in self:
            desc = str(task.description or '')
            items = []
            for block in re.findall(r'<ul[^>]*o_checklist[^>]*>(.*?)</ul>', desc, re.S):
                for li in re.findall(r'<li[^>]*>(.*?)</li>', block, re.S):
                    text = re.sub(r'<[^>]+>', '', li).strip()
                    if text:
                        items.append(text)
            new_desc = re.sub(r'<ul[^>]*o_checklist[^>]*>.*?</ul>', '', desc, flags=re.S)
            if items:
                section = self.env['steelhouse.task.section'].create({
                    'task_id': task.id, 'name': '', 'sequence': (task.sh_section_ids[-1:].sequence or 0) + 10})
                for name in items:
                    self.with_context(sh_flow_internal=True).create({
                        'name': name, 'parent_id': task.id, 'project_id': task.project_id.id,
                        'sh_section_id': section.id, 'user_ids': [(6, 0, [])], 'display_in_project': False})
            if new_desc != desc:
                task.with_context(sh_flow_internal=True).description = Markup(new_desc)

    def _compute_sh_steps(self):
        for task in self:
            task.sh_steps = ''

    # ------------------------------------------------------------------
    # Data for the "ქვედავალებები" widget (static/src/task_steps)
    # ------------------------------------------------------------------
    def _sh_item(self, sub):
        return {
            'id': sub.id,
            'name': sub.name,
            'user_id': sub.user_ids[:1].id or False,
            'user_name': sub.user_ids[:1].name or '',
            'deadline': sub.date_deadline and fields.Datetime.context_timestamp(sub, sub.date_deadline).strftime('%Y-%m-%d') or '',
            'done': sub.state == '1_done',
            'done_by': sub.sh_done_user_id.name or '',
            'done_date': sub.sh_done_date and fields.Datetime.context_timestamp(sub, sub.sh_done_date).strftime('%d.%m.%Y, %H:%M') or '',
        }

    def sh_steps_data(self):
        self.ensure_one()
        subs = self.child_ids.filtered(lambda t: t.state != '1_canceled').sorted(lambda t: (t.sequence, t.id))
        # sub-tasks without a stage (older ones): put them into a real, editable stage
        loose_subs = subs.filtered(lambda s: not s.sh_section_id or s.sh_section_id.task_id != self)
        if loose_subs:
            section = self.env['steelhouse.task.section'].create({'task_id': self.id, 'name': '', 'sequence': 0})
            loose_subs.with_context(sh_flow_internal=True).write({'sh_section_id': section.id})
            self.invalidate_recordset(['sh_section_ids'])
        sections = []
        for section in self.sh_section_ids:
            items = [self._sh_item(s) for s in subs if s.sh_section_id == section]
            sections.append({'id': section.id, 'name': section.name or '', 'items': items,
                             'user_id': section.user_id.id or False,
                             'done_date': section.done_date and fields.Datetime.context_timestamp(section, section.done_date).strftime('%d.%m.%Y, %H:%M') or '',
                             'deadline': section.date_deadline and section.date_deadline.strftime('%Y-%m-%d') or ''})
        users = self.env['res.users'].search([('share', '=', False)], order='name')
        return {
            'sections': sections,
            'users': [{'id': u.id, 'name': u.name} for u in users],
            'readonly': not self.id,
        }

    def sh_steps_add_section(self):
        self.ensure_one()
        last = self.sh_section_ids[-1:].sequence or 0
        return self.env['steelhouse.task.section'].create({'task_id': self.id, 'name': '', 'sequence': last + 10}).id

    def sh_steps_rename_section(self, section_id, name):
        self.ensure_one()
        self.sh_section_ids.filtered(lambda s: s.id == section_id).write({'name': (name or '').strip()})
        return True

    def sh_steps_write_section(self, section_id, vals):
        self.ensure_one()
        clean = {}
        if 'user_id' in vals:
            clean['user_id'] = vals['user_id'] or False
        if 'deadline' in vals:
            clean['date_deadline'] = vals['deadline'] or False
        self.sh_section_ids.filtered(lambda s: s.id == section_id).write(clean)
        return True

    def sh_steps_delete_section(self, section_id):
        self.ensure_one()
        section = self.sh_section_ids.filtered(lambda s: s.id == section_id)
        if section.subtask_ids.filtered(lambda t: t.state != '1_canceled'):
            raise UserError(_("ეტაპში ქვედავალებებია - ჯერ ისინი წაშალეთ."))
        section.unlink()
        return True

    def sh_steps_add_item(self, section_id):
        self.ensure_one()
        first = self.project_id.type_ids.filtered(lambda s: s.sh_kind == 'new')[:1]
        vals = {
            'name': _('ახალი ქვედავალება'),
            'parent_id': self.id,
            'project_id': self.project_id.id,
            'sh_project_id': self.sh_project_id.id,
            'sh_section_id': section_id or False,
            'user_ids': [(6, 0, [])],
            'reviewer_ids': [(6, 0, self.reviewer_ids.ids)],
            'display_in_project': False,
        }
        if first:
            vals['stage_id'] = first.id
        new = self.env['project.task'].with_context(sh_flow_internal=True).create(vals)
        new.sh_section_id._sh_update_done()
        return new.id

    def _sh_my_sub(self, sub_id):
        sub = self.child_ids.filtered(lambda t: t.id == sub_id)
        if not sub:
            raise UserError(_("ქვედავალება ვერ მოიძებნა."))
        return sub

    def sh_steps_write_item(self, sub_id, vals):
        self.ensure_one()
        sub = self._sh_my_sub(sub_id)
        clean = {}
        if 'name' in vals:
            clean['name'] = (vals['name'] or '').strip() or _('ქვედავალება')
        if 'user_id' in vals:
            clean['user_ids'] = [(6, 0, [vals['user_id']] if vals['user_id'] else [])]
        if 'deadline' in vals:
            clean['date_deadline'] = vals['deadline'] or False
        sub.with_context(sh_flow_internal=True).write(clean)
        return True

    def sh_steps_toggle(self, sub_id, done):
        self.ensure_one()
        sub = self._sh_my_sub(sub_id)
        if done:
            vals = {'state': '1_done', 'sh_done_user_id': self.env.user.id, 'sh_done_date': fields.Datetime.now()}
        else:
            vals = {'state': '01_in_progress', 'sh_done_user_id': False, 'sh_done_date': False}
        sub.with_context(sh_flow_internal=True).write(vals)
        sub.sh_section_id._sh_update_done()
        sub.message_post(body=_("შესრულებულად მოინიშნა") if done else _("დაბრუნდა შეუსრულებელში"),
                         message_type='notification', subtype_xmlid='mail.mt_note')
        return True

    def sh_steps_delete_item(self, sub_id):
        self.ensure_one()
        sub = self._sh_my_sub(sub_id)
        section = sub.sh_section_id
        sub.unlink()
        section._sh_update_done()
        return True
