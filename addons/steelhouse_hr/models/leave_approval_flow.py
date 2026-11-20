"""Who approves a time off request (HR's process, Docs/HR "შვებულების პროცესი", 2026-11-20):

- first approval ("პირველი დამტკიცება"): the employee's direct head(s) - equal heads all approve;
- an employee whose heads include the final approver (the founder - the department heads right under
  "ფოლადის სახლი", where დავითი and ზეზვა სალთხუციშვილი are the heads): only the founder approves,
  once (his approval goes straight to "approved");
- the founders themselves (heads of the top department "ფოლადის სახლი", no head above them): the
  final approver approves their time off with one approval (his own too);
- any other employee without a head: HR (the company's "HR" user) does not decide - HR invites the person
  who approves (field "დამმტკიცებელი (HR-ის მოწვეული)"); that person gives the first approval;
- second approval ("მეორე დამტკიცება"): only the time off type's responsible (the founder);
- HR officers no longer approve just because of their rights (they see every request);
  a system administrator still can (until the launch).
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

HR_TODO = "აირჩიეთ დამმტკიცებელი"


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_hr_user_id = fields.Many2one(
        'res.users', string='HR (შვებულებები)',
        help="ვინ იწვევს დამმტკიცებელს იმ თანამშრომლის შვებულებაზე, ვისაც ხელმძღვანელი არ ჰყავს.")


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    sh_invited_approver_id = fields.Many2one(
        'res.users', string='დამმტკიცებელი (HR-ის მოწვეული)', copy=False, tracking=True,
        domain=[('share', '=', False)],
        help="თანამშრომელს ხელმძღვანელი არ ჰყავს: HR ირჩევს, ვინ დაამტკიცებს პირველ საფეხურზე.")
    sh_no_head = fields.Boolean(compute='_compute_sh_no_head')
    sh_is_hr = fields.Boolean(compute='_compute_sh_no_head')

    @api.depends('employee_id')
    @api.depends_context('uid')
    def _compute_sh_no_head(self):
        user = self.env.user
        for leave in self:
            employee = leave.employee_id.sudo()
            leave.sh_no_head = bool(employee) and not employee._sh_heads() and not leave._sh_is_founder()
            hr = (employee.company_id or self.env.company).sh_hr_user_id
            leave.sh_is_hr = user == hr or user.has_group('base.group_system')

    # ------------------------------------------------------------------ who approves
    def _sh_final_users(self):
        # archived users count too (else an archived founder would fall back to the first step)
        return self.sudo().with_context(active_test=False).holiday_status_id.responsible_ids

    def _sh_is_founder(self):
        """The employee heads a top-level department and has no head himself."""
        employee = self.employee_id.sudo()
        return bool(employee) and not employee._sh_heads() and bool(self.env['hr.department'].sudo().search_count(
            [('parent_id', '=', False), ('manager_ids', 'in', employee.ids)]))

    def _sh_single_final(self, user):
        """One approval by the final approver is enough: he is the employee's own head, or a founder's."""
        return user in self._sh_final_users() and (
            user in self.employee_id.sudo()._sh_heads().user_id or self._sh_is_founder())

    def _get_responsible_for_approval(self):
        responsible = super()._get_responsible_for_approval()
        if self.validation_type == 'manager' or (self.validation_type == 'both' and self.state == 'confirm'):
            if self.validation_type == 'both' and self._sh_is_founder():
                responsible = self._sh_final_users()
            elif self.sh_no_head:
                responsible = self.sudo().sh_invited_approver_id
            elif self.validation_type == 'both':
                final = self._sh_final_users()
                heads = self.employee_id.sudo()._sh_heads().user_id
                if heads & final:
                    responsible = heads & final
                elif responsible - final:
                    responsible -= final
        elif self.validation_type == 'both' and self.state == 'validate1':
            responsible = self._sh_final_users() or responsible
        return responsible

    def _check_double_validation_rules(self, employees, state):
        """Odoo: only time off officers give the last approval, only the employee's time off manager the
        first one. Here: the founder on the requests he finally approves, the invited person on hers."""
        user = self.env.user
        if state == 'validate' and self and all(user in leave._sh_final_users() for leave in self):
            return
        if state == 'validate1':
            invited = self.filtered(lambda l: l.sh_no_head and l.sudo().sh_invited_approver_id == user)
            employees = employees - invited.employee_id
        return super()._check_double_validation_rules(employees, state)

    def _sh_user_can_approve(self, user):
        """Same rule for the button, the check and the counter."""
        self.ensure_one()
        if user.has_group('base.group_system'):
            return self.state in ('confirm', 'validate1')
        if self.validation_type not in ('manager', 'both'):
            return None   # other types: Odoo's own rule
        if self.state == 'confirm':
            required = self.sudo().with_context(sh_all_heads=True)._get_responsible_for_approval()
            return user in required and user not in self.sudo().sh_head_approved_user_ids
        if self.state == 'validate1':
            return user in self._sh_final_users()
        return False

    def _get_next_states_by_state(self):
        """Odoo lets only time off officers give the last approval of a two-step request: the founder
        (the type's responsible) and the person HR invited get their own step too."""
        result = super()._get_next_states_by_state()
        user = self.env.user
        if self.validation_type == 'both' and user in self._sh_final_users():
            result['validate1'].update({'validate', 'refuse'})
        if self.sh_no_head and user == self.sudo().sh_invited_approver_id:
            if self.validation_type == 'both':
                result['confirm'].update({'validate1', 'refuse'})
            elif self.validation_type == 'manager':
                result['confirm'].update({'validate', 'refuse'})
        return result

    # Odoo 19: "can_approve" = the first approval (confirm -> validate1 of a two-step type),
    # "can_validate" = the last one (validate1 -> validate, or confirm -> validate of a one-step type)
    def _compute_can_approve(self):
        super()._compute_can_approve()
        user = self.env.user
        for leave in self.filtered(lambda l: l.state in ('confirm', 'validate1')):
            allowed = leave._sh_user_can_approve(user)
            if allowed is None:
                continue
            leave.can_approve = bool(allowed) and leave.state == 'confirm' and leave.validation_type == 'both'

    def _compute_can_validate(self):
        super()._compute_can_validate()
        user = self.env.user
        for leave in self.filtered(lambda l: l.state in ('confirm', 'validate1')):
            allowed = leave._sh_user_can_approve(user)
            if allowed is None:
                continue
            last_step = leave.state == 'validate1' or leave.validation_type == 'manager'
            leave.can_validate = bool(allowed) and last_step

    def action_approve(self, check_state=True):
        user = self.env.user
        if check_state and not self.env.su:
            for leave in self:
                if leave.state in ('confirm', 'validate1') and leave._sh_user_can_approve(user) is False:
                    if leave.state == 'validate1':
                        raise UserError(_("მეორე დამტკიცება შეუძლია მხოლოდ: %s",
                                          ", ".join(leave._sh_final_users().mapped('name')) or '-'))
                    if leave.sh_no_head and not leave.sudo().sh_invited_approver_id:
                        raise UserError(_("თანამშრომელს ხელმძღვანელი არ ჰყავს: ჯერ HR-მა უნდა აირჩიოს დამმტკიცებელი."))
                    raise UserError(_("ამ მოთხოვნის დამტკიცება თქვენ არ შეგიძლიათ."))
        res = super().action_approve(check_state)
        # the founder as the employee's own head: one approval is enough
        once = self.filtered(lambda l: l.state == 'validate1' and l._sh_single_final(user))
        if once:
            once.action_approve(check_state)
        return res

    @api.model
    def sh_waiting_for_me_count(self):
        user = self.env.user
        res = super().sh_waiting_for_me_count()
        leaves = self.sudo().search([('state', 'in', ['confirm', 'validate1']),
                                     ('validation_type', 'in', ['manager', 'both']),
                                     ('employee_id.user_id', '!=', user.id)])
        mine = sum(1 for leave in leaves if leave._sh_user_can_approve(user))
        if res == -1 and not mine:
            return -1
        return mine

    # ------------------------------------------------------------------ HR invites the approver
    def _sh_hr_todo(self):
        """No head and nobody invited yet: a to-do for HR; removed once someone is invited."""
        todo = self.env.ref('mail.mail_activity_data_todo')
        for leave in self.sudo():
            hr = (leave.employee_id.company_id or self.env.company).sh_hr_user_id
            mine = leave.activity_ids.filtered(lambda a: a.activity_type_id == todo and a.user_id == hr
                                               and a.summary == HR_TODO)
            need = (leave.state == 'confirm' and leave.sh_no_head and not leave.sh_invited_approver_id
                    and leave.validation_type in ('manager', 'both'))
            if need and hr and not mine:
                leave.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=hr.id, summary=HR_TODO,
                    note=_("%(employee)s-ს ხელმძღვანელი არ ჰყავს - მოიწვიეთ, ვინ დაამტკიცებს.",
                           employee=leave.employee_id.name))
            elif not need and mine:
                mine.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._sh_hr_todo()
        return leaves

    def write(self, vals):
        if 'sh_invited_approver_id' in vals and not self.env.su:
            for leave in self:
                if not leave.sh_is_hr:
                    raise UserError(_("დამმტკიცებელს იწვევს მხოლოდ HR."))
        res = super().write(vals)
        if 'sh_invited_approver_id' in vals:
            for leave in self.filtered('sh_invited_approver_id'):
                leave.sudo().message_post(body=Markup("<p>%s</p>") % _(
                    "HR-მა დამმტკიცებლად მოიწვია: %s", leave.sudo().sh_invited_approver_id.name))
            self.env['hr.leave']._sh_sync_approval_activities()
        if 'sh_invited_approver_id' in vals or 'state' in vals or 'employee_id' in vals:
            self._sh_hr_todo()
        return res
