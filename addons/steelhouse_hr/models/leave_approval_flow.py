"""Who approves a time off request (HR's process, Docs/HR "შვებულების პროცესი", 2026-11-20):

- first approval ("პირველი დამტკიცება"): the employee's direct head(s) - equal heads all approve;
- the employee card's time off approver ("სამუშაო ინფორმაცია" - "დამმტკიცებლები" - "შვებულება"), set by
  HR in advance, wins when it is someone else than the heads (e.g. მარიამ პაპაშვილი -> სოფიკო ერაძე);
  an employee without a head is approved by that person; nobody there -> the request is not created
  ("მიმართეთ HR-ს");
- when the first approvers are the final approver himself (the department heads right under
  "ფოლადის სახლი", the founders' own time off, or the card says ზეზვა): one approval is enough;
- second approval ("მეორე დამტკიცება"): only the time off type's responsible (the founder);
- HR officers no longer approve just because of their rights (they see every request);
  a system administrator still can (until the launch).
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    # no longer used (HR sets the approver on the employee card in advance); kept for the column
    sh_hr_user_id = fields.Many2one('res.users', string='HR (შვებულებები)')


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    sh_no_head = fields.Boolean(compute='_compute_sh_no_head')
    sh_approval_path = fields.Char(
        string='დაამტკიცებს', compute='_compute_sh_approval_path',
        help="ვინ დაამტკიცებს ამ მოთხოვნას: პირველი და (ორსაფეხურიანზე) მეორე დამტკიცება.")

    @api.depends('employee_id')
    def _compute_sh_no_head(self):
        for leave in self:
            employee = leave.employee_id.sudo()
            leave.sh_no_head = bool(employee) and not employee._sh_heads() and not leave._sh_is_founder()

    @api.depends('employee_id', 'holiday_status_id', 'state')
    def _compute_sh_approval_path(self):
        for leave in self:
            leave.sh_approval_path = leave._sh_approval_text()

    # ------------------------------------------------------------------ who approves
    def _sh_final_users(self):
        # archived users count too (else an archived founder would fall back to the first step)
        return self.sudo().with_context(active_test=False).holiday_status_id.responsible_ids

    def _sh_is_founder(self):
        """The employee heads a top-level department and has no head himself."""
        employee = self.employee_id.sudo()
        return bool(employee) and not employee._sh_heads() and bool(self.env['hr.department'].sudo().search_count(
            [('parent_id', '=', False), ('manager_ids', 'in', employee.ids)]))

    def _sh_stage1_users(self):
        """First approvers (also before the request is saved; a head on leave -> his deputy)."""
        employee = self.employee_id.sudo()
        final = self._sh_final_users()
        if self.validation_type == 'both' and self._sh_is_founder():
            return final
        heads = employee._sh_heads().user_id
        card = employee.leave_manager_id
        if self.sh_no_head or (card and card not in heads):
            base = card
        else:
            base = heads or card
        result = self.env['res.users']
        for user in base:
            head = user.sudo().employee_id
            absence = head and head._sh_current_absence()
            deputy = absence and absence._sh_deputy_for(employee)
            result |= deputy.user_id if deputy and deputy.user_id and deputy != employee else user
        if self.validation_type == 'both' and result & final:
            return result & final
        return result

    def _sh_single_final(self, user):
        """One approval is enough: the first approvers are the final approver himself."""
        final = self._sh_final_users()
        first = self._sh_stage1_users()
        return user in final and bool(first) and first <= final

    def _get_responsible_for_approval(self):
        responsible = super()._get_responsible_for_approval()
        if self.validation_type == 'manager' or (self.validation_type == 'both' and self.state == 'confirm'):
            responsible = self._sh_stage1_users()
            if self.state == 'confirm' and not self.env.context.get('sh_all_heads'):
                responsible -= self.sudo().sh_head_approved_user_ids
        elif self.validation_type == 'both' and self.state == 'validate1':
            responsible = self._sh_final_users() or responsible
        return responsible

    def _sh_approval_text(self):
        self.ensure_one()
        if not self.employee_id or not self.holiday_status_id:
            return False
        names = lambda users: ", ".join(users.mapped('name')) or '-'
        kind = self.validation_type
        if kind == 'no_validation':
            return "დამტკიცება არ სჭირდება"
        final = self._sh_final_users()
        if kind == 'hr':
            return names(final) if final else "HR"
        first = self._sh_stage1_users()
        if not first:
            return "დამმტკიცებელი არ არის მითითებული - მიმართეთ HR-ს"
        if kind == 'both' and first <= final:
            return "%s (ერთი დასტურით)" % names(first)
        if kind == 'manager':
            return names(first)
        return "1. %s → 2. %s" % (names(first), names(final) if final else "HR")

    def _check_double_validation_rules(self, employees, state):
        """Odoo: only time off officers give the last approval; here the founder too, on his requests."""
        user = self.env.user
        if state == 'validate' and self and all(user in leave._sh_final_users() for leave in self):
            return
        return super()._check_double_validation_rules(employees, state)

    def _sh_user_can_approve(self, user):
        """Same rule for the button, the check and the counter."""
        self.ensure_one()
        if user.has_group('base.group_system'):
            return self.state in ('confirm', 'validate1')
        if self.validation_type == 'hr':
            # approved directly by the type's responsible (e.g. compensatory days - the founder)
            final = self._sh_final_users()
            if not final:
                return None
            return self.state == 'confirm' and user in final
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
        (the type's responsible) gets it too."""
        result = super()._get_next_states_by_state()
        if self.validation_type == 'both' and self.env.user in self._sh_final_users():
            result['validate1'].update({'validate', 'refuse'})
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
            last_step = leave.state == 'validate1' or leave.validation_type in ('manager', 'hr')
            leave.can_validate = bool(allowed) and last_step

    def action_approve(self, check_state=True):
        user = self.env.user
        if check_state and not self.env.su:
            for leave in self:
                if leave.state in ('confirm', 'validate1') and leave._sh_user_can_approve(user) is False:
                    if leave.state == 'validate1':
                        raise UserError(_("მეორე დამტკიცება შეუძლია მხოლოდ: %s",
                                          ", ".join(leave._sh_final_users().mapped('name')) or '-'))
                    raise UserError(_("ამ მოთხოვნის დამტკიცება თქვენ არ შეგიძლიათ."))
        res = super().action_approve(check_state)
        # the final approver was also the first one: one approval is enough
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

    # ------------------------------------------------------------------ nobody to approve
    def _sh_check_has_approver(self):
        for leave in self:
            if (leave.state == 'confirm' and leave.validation_type in ('manager', 'both')
                    and leave.employee_id and not leave._sh_stage1_users()):
                raise UserError(_("%s: ბარათზე შვებულების დამმტკიცებელი არ არის მითითებული - მიმართეთ HR-ს "
                                  "(ბარათი: „სამუშაო ინფორმაცია“ - „დამმტკიცებლები“ - „შვებულება“).",
                                  leave.employee_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._sh_check_has_approver()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        if 'employee_id' in vals or 'holiday_status_id' in vals:
            self._sh_check_has_approver()
        return res


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    def _sh_final_users(self):
        return self.sudo().with_context(active_test=False).holiday_status_id.responsible_ids

    def _sh_user_can_approve(self, user):
        """Days requests of a type approved "by HR" with a responsible set (compensatory days): only the
        responsible (the founder) or a system administrator; other cases - Odoo's own rule."""
        self.ensure_one()
        if self.state not in ('confirm', 'validate1'):
            return None
        if user.has_group('base.group_system'):
            return True
        final = self._sh_final_users()
        if self.validation_type != 'hr' or not final:
            return None
        return user in final

    def _compute_can_approve(self):
        super()._compute_can_approve()
        for allocation in self:
            allowed = allocation._sh_user_can_approve(self.env.user)
            if allowed is False:
                allocation.can_approve = False

    def _compute_can_validate(self):
        super()._compute_can_validate()
        for allocation in self:
            allowed = allocation._sh_user_can_approve(self.env.user)
            if allowed is False:
                allocation.can_validate = False

    def action_approve(self):
        if not self.env.su:
            for allocation in self:
                if allocation._sh_user_can_approve(self.env.user) is False:
                    raise UserError(_("ამ მოთხოვნის დამტკიცება შეუძლია მხოლოდ: %s",
                                      ", ".join(allocation._sh_final_users().mapped('name'))))
        return super().action_approve()
