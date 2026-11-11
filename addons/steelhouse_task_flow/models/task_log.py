from markupsafe import Markup, escape

from odoo import api, fields, models, _

# Fields written to the task history ("ისტორია"), in display order, with Georgian labels
LOGGED = [
    ('name', 'სახელი'),
    ('stage_id', 'ეტაპი'),
    ('state', 'სტატუსი'),
    ('priority', 'პრიორიტეტი'),
    ('project_id', 'დეპარტამენტი'),
    ('sh_project_id', 'პროექტი'),
    ('partner_id', 'კლიენტი'),
    ('sh_responsible_id', 'მთავარი პასუხისმგებელი'),
    ('user_ids', 'შემსრულებლები'),
    ('reviewer_ids', 'შემმოწმებლები'),
    ('sh_work_start', 'სამუშაოს დაწყება'),
    ('date_deadline', 'დასრულების თარიღი'),
    ('sh_category', 'კატეგორია'),
    ('sh_branch', 'ფილიალი'),
    ('sh_manual_progress', 'ხელით პროგრესი (%)'),
    ('hold_reason', 'შეჩერების მიზეზი'),
    ('hold_date', 'შეჩერდა'),
    ('resume_date', 'განახლება'),
    ('return_reason', 'დაბრუნების მიზეზი'),
    ('cancel_reason', 'გაუქმების მიზეზი'),
    ('sh_repeat', 'განმეორებადი'),
    ('sh_repeat_interval', 'განმეორდეს ყოველ'),
    ('sh_repeat_unit', 'ერთეული'),
    ('sh_repeat_start', 'ციკლის დაწყება'),
    ('sh_repeat_until_type', 'ვადამდე'),
    ('sh_repeat_until', 'ბოლო თარიღი'),
    ('sh_final_note', 'საბოლოო აღწერა'),
    ('sh_final_attachment_ids', 'საბოლოო ფაილები'),
    ('description', 'აღწერა'),
]

STYLE = {
    'on_hold': ('⏸', 'დავალება შეჩერდა', '#e0a800', '#fffbea'),
    'returned': ('↩', 'დავალება დაბრუნდა შესასწორებლად', '#e8590c', '#fff4ec'),
    'cancelled': ('✖', 'დავალება გაუქმდა', '#6c757d', '#f4f5f6'),
    'done': ('✔', 'დავალება დასრულდა (შემოწმებულია)', '#28a745', '#f1fbf3'),
    'accepted': ('✋', 'დავალება მიღებულია', '#3d85c6', '#f2f7fc'),
    'review': ('➜', 'გადავიდა შემოწმებაზე', '#7d5ba6', '#f6f2fb'),
    'stage': ('➜', 'ეტაპი შეიცვალა', '#3d85c6', '#f2f7fc'),
    'edit': ('✏', 'შეიცვალა', '#3d85c6', '#ffffff'),
    'steps': ('☑', 'ქვედავალებები', '#20a8a0', '#f0fbfa'),
    'files': ('📎', 'ფაილები', '#6c757d', '#ffffff'),
}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # ------------------------------------------------------------------
    def _sh_fmt(self, fname, value):
        field = self._fields[fname]
        if value in (False, None, '') or (hasattr(value, '_name') and not value):
            return '—'
        if field.type == 'many2one':
            return value.display_name
        if field.type in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name')) or '—'
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, value)
        if field.type == 'date':
            return value.strftime('%d.%m.%Y')
        if field.type == 'datetime':
            return fields.Datetime.context_timestamp(self, value).strftime('%d.%m.%Y, %H:%M')
        if field.type == 'boolean':
            return _('დიახ') if value else _('არა')
        if field.type == 'html':
            return _('შეიცვალა')
        return str(value)

    def _sh_snapshot(self, names):
        return {task.id: {n: task[n] for n in names} for task in self}

    @api.model
    def _sh_log_body(self, kind, lines):
        icon, title, border, bg = STYLE[kind]
        rows = Markup('').join(Markup('<div style="margin-top:2px">%s</div>') % line for line in lines)
        return Markup(
            '<div style="border-left:4px solid %s;background:%s;padding:4px 10px;border-radius:3px">'
            '<div style="font-weight:700">%s %s</div>%s</div>') % (border, bg, icon, title, rows)

    def _sh_log(self, kind, lines):
        for task in self:
            task.message_post(body=self._sh_log_body(kind, lines), message_type='notification',
                              subtype_xmlid='mail.mt_note')

    def write(self, vals):
        ctx = self.env.context
        names = [n for n, _l in LOGGED if n in vals and n in self._fields]
        if 'stage_id' in vals:  # set by the flow during a stage change (resume date...)
            names = [n for n, _l in LOGGED if n in names or n in ('resume_date', 'hold_date')]
        if not names or ctx.get('sh_no_log') or ctx.get('sh_logging'):
            return super().write(vals)
        before = self._sh_snapshot(names)
        res = super(ProjectTask, self.with_context(sh_logging=True, mail_notrack=True)).write(vals)
        labels = dict(LOGGED)
        for task in self:
            old = before.get(task.id, {})
            lines, kind = [], 'edit'
            for name in names:
                new_value = task[name]
                old_value = old.get(name)
                if name == 'description':
                    if (str(old_value or '') != str(new_value or '')):
                        lines.append(Markup('%s: <b>%s</b>') % (labels[name], _('შეიცვალა')))
                    continue
                if old_value == new_value:
                    continue
                if name == 'state' and 'stage_id' in names and old.get('stage_id') != task.stage_id:
                    continue  # the stage line already says it
                if name == 'stage_id':
                    kind = task.stage_id.sh_kind if task.stage_id.sh_kind in STYLE else 'stage'
                    if kind in ('new', 'in_progress'):
                        kind = 'stage'
                lines.append(Markup('%s: <span style="color:#999;text-decoration:line-through">%s</span> → <b>%s</b>') % (
                    labels[name], task._sh_fmt(name, old_value), task._sh_fmt(name, new_value)))
            if lines:
                # stage line first
                task._sh_log(kind, lines)
        return res

    # ------------------------------------------------------------------
    # Sub-task stages ("ქვედავალებები" tab): log on the parent task
    # ------------------------------------------------------------------
    def _sh_step_log(self, text):
        self._sh_log('steps', [text])

    def sh_steps_add_section(self):
        res = super().sh_steps_add_section()
        self._sh_step_log(_("დაემატა ახალი ეტაპი"))
        return res

    def sh_steps_rename_section(self, section_id, name):
        section = self.sh_section_ids.filtered(lambda s: s.id == section_id)
        old = section.name
        res = super().sh_steps_rename_section(section_id, name)
        if (old or '') != (name or '').strip():
            self._sh_step_log(Markup('ეტაპის სახელი: <span style="color:#999;text-decoration:line-through">%s</span> → <b>%s</b>') % (old or '—', (name or '').strip() or '—'))
        return res

    def sh_steps_write_section(self, section_id, vals):
        section = self.sh_section_ids.filtered(lambda s: s.id == section_id)
        old_user, old_date = section.user_id, section.date_deadline
        res = super().sh_steps_write_section(section_id, vals)
        label = section.name or '—'
        if 'user_id' in vals and section.user_id != old_user:
            self._sh_step_log(Markup('„%s“ — პასუხისმგებელი: %s → <b>%s</b>') % (label, old_user.name or '—', section.user_id.name or '—'))
        if 'deadline' in vals and section.date_deadline != old_date:
            fmt = lambda d: d.strftime('%d.%m.%Y') if d else '—'
            self._sh_step_log(Markup('„%s“ — ვადა: %s → <b>%s</b>') % (label, fmt(old_date), fmt(section.date_deadline)))
        return res

    def sh_steps_delete_section(self, section_id):
        name = self.sh_section_ids.filtered(lambda s: s.id == section_id).name
        res = super().sh_steps_delete_section(section_id)
        self._sh_step_log(Markup('წაიშალა ეტაპი: <b>%s</b>') % (name or '—'))
        return res

    def sh_steps_add_item(self, section_id):
        res = super().sh_steps_add_item(section_id)
        section = self.env['steelhouse.task.section'].browse(section_id)
        self._sh_step_log(Markup('„%s“ — დაემატა ქვედავალება') % (section.name or '—'))
        return res

    def sh_steps_write_item(self, sub_id, vals):
        sub = self._sh_my_sub(sub_id)
        old = {'name': sub.name, 'user': sub.user_ids[:1].name, 'date': sub.date_deadline}
        res = super().sh_steps_write_item(sub_id, vals)
        sub.invalidate_recordset()
        if 'name' in vals and sub.name != old['name']:
            self._sh_step_log(Markup('ქვედავალება: %s → <b>%s</b>') % (old['name'], sub.name))
        if 'user_id' in vals and sub.user_ids[:1].name != old['user']:
            self._sh_step_log(Markup('„%s“ — შემსრულებელი: %s → <b>%s</b>') % (sub.name, old['user'] or '—', sub.user_ids[:1].name or '—'))
        if 'deadline' in vals and sub.date_deadline != old['date']:
            fmt = lambda d: fields.Datetime.context_timestamp(self, d).strftime('%d.%m.%Y') if d else '—'
            self._sh_step_log(Markup('„%s“ — ვადა: %s → <b>%s</b>') % (sub.name, fmt(old['date']), fmt(sub.date_deadline)))
        return res

    def sh_steps_toggle(self, sub_id, done):
        res = super().sh_steps_toggle(sub_id, done)
        sub = self._sh_my_sub(sub_id)
        text = _('შესრულდა') if done else _('დაბრუნდა შეუსრულებელში')
        self._sh_step_log(Markup('„%s“ → <b>%s</b>') % (sub.name, text))
        return res

    def sh_steps_delete_item(self, sub_id):
        name = self._sh_my_sub(sub_id).name
        res = super().sh_steps_delete_item(sub_id)
        self._sh_step_log(Markup('წაიშალა ქვედავალება: <b>%s</b>') % name)
        return res


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for att in records.filtered(lambda a: a.res_model == 'project.task' and a.res_id):
            task = self.env['project.task'].browse(att.res_id).exists()
            if task:
                task._sh_log('files', [Markup('მიმაგრდა: <b>%s</b>') % att.name])
        return records

    def unlink(self):
        logs = [(a.res_id, a.name) for a in self if a.res_model == 'project.task' and a.res_id]
        res = super().unlink()
        for res_id, name in logs:
            task = self.env['project.task'].browse(res_id).exists()
            if task:
                task._sh_log('files', [Markup('წაიშალა ფაილი: <b>%s</b>') % name])
        return res
