from markupsafe import Markup, escape

from odoo import fields, models, _
from odoo.exceptions import UserError

# Odoo task state that follows each stage kind.
KIND_STATE = {'done': '1_done', 'cancelled': '1_canceled', 'returned': '02_changes_requested'}
CLOSED = ('1_done', '1_canceled')
# Stage kinds that need a reason (entered through the wizard).
REASON_KINDS = ('on_hold', 'returned', 'cancelled')
# Stage kinds only the reviewer (or a system admin) may set.
REVIEWER_KINDS = ('done', 'returned', 'cancelled')


class ProjectTask(models.Model):
    _inherit = 'project.task'

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

    def _sh_check_evidence(self):
        Attachment = self.env['ir.attachment'].sudo()
        for task in self.filtered(lambda t: t.evidence_required and not t.is_template):
            if not Attachment.search_count([('res_model', '=', 'project.task'), ('res_id', '=', task.id)]):
                raise UserError(_(
                    "„%s“-ს სჭირდება მტკიცებულება. ჯერ მიამაგრეთ ფაილი ან ფოტო (📎), "
                    "შემდეგ გადაიყვანეთ „შემოწმებაზე“.", task.name))

    # ------------------------------------------------------------------
    def write(self, vals):
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
                    self._sh_check_evidence()
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
        return res

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
