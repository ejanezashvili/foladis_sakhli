import re
from collections.abc import Mapping

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Odoo task state that follows each stage kind.
KIND_STATE = {'done': '1_done', 'cancelled': '1_canceled', 'returned': '02_changes_requested'}
CLOSED = ('1_done', '1_canceled')
# Stage kinds that need a reason (entered through the wizard).
REASON_KINDS = ('on_hold', 'returned', 'cancelled')
# Stage kinds only the reviewer (or a system admin) may set.
REVIEWER_KINDS = ('done', 'returned', 'cancelled')
# Progress by stage kind, used when the task has no subtasks, checklist or manual value.
KIND_PROGRESS = {'new': 0, 'accepted': 10, 'in_progress': 50, 'on_hold': 50, 'returned': 50, 'review': 90}
MANUAL_PROGRESS_PROP = 'sh_progress'
CHECKLIST_ITEM = re.compile(r'<li\b([^>]*)>', re.I)


INFO_PREFIXES = ('თქვენ დაგენიშნათ',)
REMINDER_PREFIXES = INFO_PREFIXES + ('ვადა იწურება', 'ვადაგადაცილებულია', 'ესკალაცია', 'დასადასტურებელია')


# "კლიენტი" (customer): employees and internal users are not customers
SH_CUSTOMER_DOMAIN = ("['&', '|', ('company_id', '=?', company_id), ('company_id', '=', False), "
                      "'&', ('employee_ids', '=', False), '|', ('user_ids', '=', False), ('user_ids.share', '=', True)]")


class ProjectTask(models.Model):
    _inherit = 'project.task'

    partner_id = fields.Many2one(domain=SH_CUSTOMER_DOMAIN)

    # project_id is shown as "დეპარტამენტი" (department project: stages / flow, rights);
    # "პროექტი" is the concrete project the task also belongs to
    sh_project_id = fields.Many2one(
        'project.project', string='პროექტი', index=True, tracking=True,
        domain="[('sh_is_department', '=', False), ('is_template', '=', False)]",
        help="კონკრეტული პროექტი. დავალება ჩანს დეპარტამენტშიც და ამ პროექტშიც, ერთი ფლოუთი.")

    sh_department_id = fields.Many2one(
        related='project_id.sh_department_id', string='HR დეპარტამენტი', store=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        # a sub-task belongs to the same concrete project as its parent
        for vals in vals_list:
            if vals.get('parent_id') and 'sh_project_id' not in vals:
                vals['sh_project_id'] = self.browse(vals['parent_id']).sh_project_id.id
        return super().create(vals_list)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Kanban of a concrete project: show the department flow columns even when empty."""
        stages = super()._read_group_stage_ids(stages, domain)
        if self.env.context.get('sh_project_view') or self.env.context.get('sh_all_tasks'):
            stages |= self.env['project.project'].search([('sh_is_department', '=', True)]).type_ids
            stages = stages.sorted(lambda s: (s.sequence, s.id))
        return stages

    sh_kind = fields.Selection(related='stage_id.sh_kind', string='სტადიის ტიპი')
    reviewer_id = fields.Many2one(
        'res.users', string='შემმოწმებელი', tracking=True, index=True,
        default=lambda self: self.env.user, domain="[('share', '=', False)]",
        help="ადასტურებს შესრულებას (დასრულება), აბრუნებს ან აუქმებს დავალებას.")
    evidence_required = fields.Boolean(
        'საჭიროა მტკიცებულება', tracking=True,
        help="შემოწმებაზე გადაყვანამდე დავალებაზე ფაილი ან ფოტო უნდა იყოს მიმაგრებული.")
    hold_reason = fields.Text('შეჩერების მიზეზი', copy=False, tracking=True)
    resume_date = fields.Date('განახლების თარიღი', copy=False, tracking=True)
    return_reason = fields.Text('დაბრუნების მიზეზი', copy=False, tracking=True)
    cancel_reason = fields.Text('გაუქმების მიზეზი', copy=False, tracking=True)
    # former task properties, now real fields (same in every department, searchable, tracked)
    sh_responsible_id = fields.Many2one(
        'res.users', string='მთავარი პასუხისმგებელი', tracking=True, index=True,
        domain="[('share', '=', False)]")
    sh_work_start = fields.Date('სამუშაოს დაწყება', tracking=True)
    sh_category = fields.Selection([
        ('admin', 'ადმინისტრაციული'), ('sales', 'გაყიდვები'), ('stock', 'მარაგი და საწყობი'),
        ('finance', 'ფინანსური'), ('tech', 'ტექნიკური'), ('other', 'სხვა'),
    ], string='კატეგორია', tracking=True)
    sh_branch = fields.Selection([
        ('main', 'ძირითადი ფილიალი'), ('vaziani3', 'ვაზიანი #3'), ('vaziani1', 'ვაზიანი 1'),
        ('vaziani2', 'ვაზიანი 2'), ('batumi', 'ბათუმის ფილიალი'), ('lilo', 'ლილო'),
    ], string='ფილიალი', tracking=True)
    sh_manual_progress = fields.Integer('ხელით პროგრესი (%)', tracking=True)
    sh_progress = fields.Integer(
        'პროგრესი (%)', compute='_compute_sh_progress', store=True,
        help="ავტომატურად: დასრულებული = 100%; სხვა შემთხვევაში ქვედავალებების, საკონტროლო სიისა და "
             "ხელით პროგრესის საშუალო; თუ არცერთი არ არის — სტადიით. „შემოწმებაზე“ — მინიმუმ 90%.")

    # ------------------------------------------------------------------
    # Automatic progress (requirement 3.3)
    # ------------------------------------------------------------------
    @staticmethod
    def _sh_checklist_percent(html):
        """Share of checked items in the description's checklists, or None if there is no checklist."""
        if not html or 'o_checklist' not in html:
            return None
        total = done = 0
        for block in re.findall(r'<ul\b[^>]*o_checklist[^>]*>(.*?)</ul>', html, re.S | re.I):
            for attrs in CHECKLIST_ITEM.findall(block):
                total += 1
                if 'o_checked' in attrs:
                    done += 1
        return round(100 * done / total) if total else None

    def _sh_manual_percent(self):
        value = self.sh_manual_progress
        return max(0, min(100, value)) if value else None

    @api.depends('stage_id.sh_kind', 'state', 'child_ids.state', 'description', 'sh_manual_progress')
    def _compute_sh_progress(self):
        for task in self:
            kind = task.stage_id.sh_kind
            if kind == 'done' or task.state == '1_done':
                task.sh_progress = 100
                continue
            sources = []
            subtasks = task.child_ids.filtered(lambda t: t.state != '1_canceled')
            if subtasks:
                sources.append(100 * len(subtasks.filtered(lambda t: t.state == '1_done')) / len(subtasks))
            checklist = self._sh_checklist_percent(task.description and str(task.description))
            if checklist is not None:
                sources.append(checklist)
            manual = task._sh_manual_percent()
            if manual is not None:
                sources.append(manual)
            value = round(sum(sources) / len(sources)) if sources else KIND_PROGRESS.get(kind, 0)
            if kind == 'review':
                value = max(value, 90)
            task.sh_progress = value

    # ------------------------------------------------------------------
    def _sh_stage_of_kind(self, kind):
        self.ensure_one()
        return self.project_id.type_ids.filtered(lambda s: s.sh_kind == kind)[:1]

    def _sh_can_review(self):
        self.ensure_one()
        user = self.env.user
        return (self.env.su or not self.reviewer_id or self.reviewer_id == user
                or user.has_group('base.group_system'))

    def _sh_check_reviewer(self, kind):
        labels = dict(self.env['project.task.type']._fields['sh_kind'].selection)
        for task in self.filtered(lambda t: not t.is_template):
            if not task._sh_can_review():
                raise UserError(_(
                    "„%(stage)s“-ში გადაყვანა შეუძლია მხოლოდ შემმოწმებელს (%(reviewer)s) "
                    "ან სისტემის ადმინისტრატორს.",
                    stage=labels.get(kind, kind), reviewer=task.reviewer_id.name))

    def _sh_check_evidence(self, new_flag=None):
        """new_flag: value of evidence_required being written in the same save (if any)."""
        Attachment = self.env['ir.attachment'].sudo()
        needs = (lambda t: new_flag) if new_flag is not None else (lambda t: t.evidence_required)
        for task in self.filtered(lambda t: needs(t) and not t.is_template):
            if not Attachment.search_count([('res_model', '=', 'project.task'), ('res_id', '=', task.id)]):
                raise UserError(_(
                    "„%s“-ს სჭირდება მტკიცებულება. ჯერ მიამაგრეთ ფაილი ან ფოტო (📎), "
                    "შემდეგ გადაიყვანეთ „შემოწმებაზე“.", task.name))

    # ------------------------------------------------------------------
    # History of task properties (Odoo does not track them; requirement 3.8)
    # ------------------------------------------------------------------
    @staticmethod
    def _sh_prop_display(prop):
        value = prop.get('value')
        if value in (False, None, '', []):
            return '—'
        ptype = prop.get('type')
        if ptype == 'many2one':
            return value[1] if isinstance(value, (list, tuple)) else str(value)
        if ptype == 'many2many':
            return ', '.join(v[1] if isinstance(v, (list, tuple)) else str(v) for v in value)
        if ptype == 'selection':
            return dict(prop.get('selection') or []).get(value, value)
        if ptype == 'tags':
            labels = {t[0]: t[1] for t in (prop.get('tags') or [])}
            return ', '.join(labels.get(v, v) for v in value)
        if ptype == 'boolean':
            return _("დიახ") if value else _("არა")
        if ptype == 'date' and isinstance(value, str):
            y, m, d = value[:10].split('-')
            return '%s/%s/%s' % (d, m, y)
        return str(value)

    def _sh_props_snapshot(self):
        return {
            rec['id']: {p['name']: (p.get('string') or p['name'], self._sh_prop_display(p))
                        for p in (rec['task_properties'] or [])}
            for rec in self.read(['task_properties'])
        }

    def _sh_log_property_changes(self, before):
        after = self._sh_props_snapshot()
        for task in self:
            old, new = before.get(task.id, {}), after.get(task.id, {})
            lines = []
            for key, (label, value) in new.items():
                old_value = old.get(key, (label, '—'))[1]
                if old_value != value:
                    lines.append(Markup("<li>%s: %s → <b>%s</b></li>") % (label, old_value, value))
            if lines:
                task.message_post(
                    body=Markup("<ul class='mb-0'>%s</ul>") % Markup('').join(lines),
                    message_type='notification', subtype_xmlid='mail.mt_note')

    # ------------------------------------------------------------------
    def write(self, vals):
        if 'task_properties' in vals and not self.env.context.get('sh_props_logging'):
            before = self._sh_props_snapshot()
            res = self.with_context(sh_props_logging=True).write(vals)
            self._sh_log_property_changes(before)
            return res
        if self.env.context.get('sh_flow_internal'):
            return super().write(vals)
        vals = dict(vals)
        kind = False
        if vals.get('stage_id'):
            kind = self.env['project.task.type'].browse(vals['stage_id']).sh_kind
            if kind:
                if kind in REASON_KINDS and not self.env.context.get('sh_reason_given'):
                    raise UserError(_(
                        "ამ სტადიაზე გადასაყვანად გამოიყენეთ ღილაკი ფორმის თავზე "
                        "(„შეჩერება“, „დაბრუნება“ ან „გაუქმება“) — საჭიროა მიზეზი."))
                if kind in REVIEWER_KINDS:
                    self._sh_check_reviewer(kind)
                if kind == 'review':
                    self._sh_check_evidence(vals.get('evidence_required') if 'evidence_required' in vals else None)
                if 'state' not in vals:
                    vals['state'] = KIND_STATE.get(kind, '01_in_progress')
        elif vals.get('state') in CLOSED:
            # Status set directly (status button): same rules, then move to the matching stage.
            kind = 'done' if vals['state'] == '1_done' else 'cancelled'
            if kind == 'cancelled' and not self.env.context.get('sh_reason_given'):
                raise UserError(_("გასაუქმებლად გამოიყენეთ ღილაკი „გაუქმება“ — საჭიროა მიზეზი."))
            self._sh_check_reviewer(kind)
        res = super().write(vals)
        if not vals.get('stage_id') and vals.get('state') in CLOSED:
            for task in self:
                stage = task._sh_stage_of_kind(kind)
                if stage and task.stage_id != stage:
                    task.with_context(sh_flow_internal=True).stage_id = stage
        if 'state' in vals or 'stage_id' in vals:
            self.filtered(lambda t: t.state in CLOSED)._sh_drop_reminders(REMINDER_PREFIXES)
        return res

    # ------------------------------------------------------------------
    # Reminders from the automation rules (block 4) are activities:
    # - "assigned" notice is informational: gone once the assignee opens the task
    # - deadline / overdue / escalation / review ones stay until done, or until the task is closed
    def _sh_drop_reminders(self, prefixes, user=None):
        acts = self.sudo().activity_ids.filtered(
            lambda a: (a.summary or '').startswith(prefixes) and (user is None or a.user_id == user))
        if acts:
            acts.unlink()

    def web_read(self, specification):
        if len(self) == 1:
            self._sh_drop_reminders(INFO_PREFIXES, user=self.env.user)
        return super().web_read(specification)

    # ------------------------------------------------------------------
    def _sh_open_wizard(self, mode):
        self.ensure_one()
        names = dict(self.env['steelhouse.task.flow.wizard']._fields['mode'].selection)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'steelhouse.task.flow.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': names[mode],
            'context': {'default_task_id': self.id, 'default_mode': mode},
        }

    def action_sh_mark_done(self):
        """Assignee marks the task done: it goes to review, the reviewer confirms it."""
        self.ensure_one()
        if self.env.user not in self.user_ids and not self.env.user.has_group('project.group_project_manager'):
            raise UserError(_("შესრულებულად მონიშვნა შეუძლია მხოლოდ დავალების შემსრულებელს."))
        stage = self._sh_stage_of_kind('review')
        if not stage:
            raise UserError(_("ამ დეპარტამენტს არ აქვს „შემოწმებაზე“ სტადია."))
        self.write({'stage_id': stage.id})
        return True

    def action_sh_hold(self):
        return self._sh_open_wizard('on_hold')

    def action_sh_return(self):
        self._sh_check_reviewer('returned')
        return self._sh_open_wizard('returned')

    def action_sh_cancel(self):
        self._sh_check_reviewer('cancelled')
        return self._sh_open_wizard('cancelled')

    def _sh_apply_reason(self, kind, reason, resume_date=False):
        self.ensure_one()
        stage = self._sh_stage_of_kind(kind)
        if not stage:
            raise UserError(_("ამ პროექტს არ აქვს შესაბამისი სტადია. დაამატეთ სტადია და მიუთითეთ მისი ტიპი."))
        vals = {'stage_id': stage.id}
        titles = {
            'on_hold': _("დავალება შეჩერდა"),
            'returned': _("დავალება დაბრუნდა შესასწორებლად"),
            'cancelled': _("დავალება გაუქმდა"),
        }
        if kind == 'on_hold':
            vals.update(hold_reason=reason, resume_date=resume_date)
        elif kind == 'returned':
            vals['return_reason'] = reason
        else:
            vals['cancel_reason'] = reason
        self.with_context(sh_reason_given=True).write(vals)
        body = Markup("<b>%s</b><br/>%s") % (titles[kind], escape(reason))
        if resume_date:
            body += Markup("<br/>%s: %s") % (_("განახლების თარიღი"), resume_date.strftime('%d/%m/%Y'))
        self.message_post(body=body, message_type='comment', subtype_xmlid='mail.mt_note')
