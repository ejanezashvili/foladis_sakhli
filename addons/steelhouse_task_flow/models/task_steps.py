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
    subtask_ids = fields.One2many('project.task', 'sh_section_id', string='ქვედავალებები')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_section_id = fields.Many2one('steelhouse.task.section', string='ეტაპი', index=True,
                                    ondelete='set null', copy=False)
    sh_section_ids = fields.One2many('steelhouse.task.section', 'task_id', string='ეტაპები')
    sh_steps = fields.Char(compute='_compute_sh_steps', string='ქვედავალებები')

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
            'done_date': sub.sh_done_date and fields.Datetime.context_timestamp(sub, sub.sh_done_date).strftime('%d.%m.%Y') or '',
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
            raise UserError(_("ეტაპში ქვედავალებებია — ჯერ ისინი წაშალეთ."))
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
        return self.env['project.task'].with_context(sh_flow_internal=True).create(vals).id

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
        sub.message_post(body=_("შესრულებულად მოინიშნა") if done else _("დაბრუნდა შეუსრულებელში"),
                         message_type='notification', subtype_xmlid='mail.mt_note')
        return True

    def sh_steps_delete_item(self, sub_id):
        self.ensure_one()
        self._sh_my_sub(sub_id).unlink()
        return True
