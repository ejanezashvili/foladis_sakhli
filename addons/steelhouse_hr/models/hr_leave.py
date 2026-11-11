from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SteelhouseLeaveDelegation(models.Model):
    _name = 'steelhouse.leave.delegation'
    _description = 'შემცვლელი შვებულების დროს'
    _order = 'leave_id, id'

    leave_id = fields.Many2one('hr.leave', string='შვებულება', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='leave_id.employee_id', string='თანამშრომელი', store=True)
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი', required=True)
    deputy_id = fields.Many2one('hr.employee', string='შემცვლელი')

    deputy_department_id = fields.Many2one(related='deputy_id.department_id', string='შემცვლელის დეპარტამენტი')

    @api.onchange('deputy_id')
    def _onchange_deputy_department(self):
        """A deputy can be picked from the whole company (people of the line's department
        are offered first). If he is not in that department (or its sub-units), the line
        takes the deputy's department."""
        for line in self:
            dep = line.deputy_id.department_id
            if dep and not (line.department_id and (dep.parent_path or '').startswith(line.department_id.parent_path or '-')):
                line.department_id = dep

    @api.onchange('department_id')
    def _onchange_department_clear_deputy(self):
        """The deputy is chosen among the employees of the line's department
        (sub-units included): changing the department drops a deputy from elsewhere."""
        for line in self:
            dep = line.deputy_id.department_id
            if line.deputy_id and not (dep and line.department_id
                                       and (dep.parent_path or '').startswith(line.department_id.parent_path or '-')):
                line.deputy_id = False

    def _sh_deputy_absence(self):
        """The deputy's own time off (approved or waiting) overlapping this request, if any."""
        self.ensure_one()
        leave = self.leave_id
        deputy = self.deputy_id._origin or self.deputy_id
        if not (deputy and leave.date_from and leave.date_to) or leave.state in ('cancel', 'refuse'):
            return self.env['hr.leave']
        domain = [('employee_id', '=', deputy.id), ('state', 'in', ['confirm', 'validate1', 'validate']),
                  ('date_from', '<', leave.date_to), ('date_to', '>', leave.date_from)]
        if isinstance(leave._origin.id, int):
            domain.append(('id', '!=', leave._origin.id))
        return self.env['hr.leave'].sudo().search(domain, limit=1)

    def _sh_absence_message(self, absence):
        status = {'confirm': 'დასამტკიცებელი', 'validate1': 'მეორე დამტკიცება', 'validate': 'დამტკიცებული'}
        dates = absence.request_date_from.strftime('%d.%m.%Y')
        if absence.request_date_to and absence.request_date_to != absence.request_date_from:
            dates += ' – ' + absence.request_date_to.strftime('%d.%m.%Y')
        return _("„%(name)s“ ამ დღეებში თვითონ არის შვებულებაში: %(type)s, %(dates)s (%(status)s). "
                 "აირჩიეთ სხვა შემცვლელი.",
                 name=absence.employee_id.name, type=absence.holiday_status_id.name, dates=dates,
                 status=status.get(absence.state, absence.state))

    @api.onchange('deputy_id')
    def _onchange_deputy_absent(self):
        for line in self:
            absence = line._sh_deputy_absence()
            if absence:
                message = line._sh_absence_message(absence)
                line.deputy_id = False
                return {'warning': {'title': _("შემცვლელი შვებულებაშია"), 'message': message}}

    @api.constrains('deputy_id', 'leave_id')
    def _check_deputy_available(self):
        for line in self:
            absence = line._sh_deputy_absence()
            if absence:
                raise ValidationError(line._sh_absence_message(absence))

    @api.constrains('deputy_id', 'employee_id')
    def _check_deputy_not_self(self):
        for line in self:
            if line.deputy_id and line.deputy_id == line.employee_id:
                raise ValidationError(_("საკუთარი თავი შემცვლელად ვერ მიუთითებთ."))

    @api.constrains('department_id', 'leave_id')
    def _check_unique_department(self):
        for line in self:
            same = line.leave_id.delegation_ids.filtered(lambda l: l.department_id == line.department_id)
            if len(same) > 1:
                raise ValidationError(_("დეპარტამენტი „%s“ ორჯერაა მითითებული.", line.department_id.name))


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    # ------------------------------------------------------------------
    # Equal heads: every head of the employee approves like Odoo's single
    # "time off approver" (first step); the first one to decide closes it.
    # ------------------------------------------------------------------
    def _sh_user_is_co_head(self):
        self.ensure_one()
        user = self.env.user
        employee = self.employee_id.sudo()
        return (employee.leave_manager_id != user and employee.user_id != user
                and user in employee.sh_head_user_ids)

    def _get_next_states_by_state(self):
        result = super()._get_next_states_by_state()
        # a refused request can be sent back to approval (instead of creating it again)
        # by its approver or any equal head; HR officers already can
        if self.validation_type != 'hr' and (self.employee_id.sudo().leave_manager_id == self.env.user
                                             or self._sh_user_is_co_head()):
            result['refuse'].add('confirm')
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user') and self._sh_user_is_co_head():
            validation_type = self.validation_type
            if validation_type != 'hr':
                result['confirm'].add('refuse')
                result['validate'].add('refuse')
            if validation_type == 'both':
                result['confirm'].add('validate1')
                result['validate1'].add('refuse')
            elif validation_type == 'manager':
                result['confirm'].add('validate')
                result['refuse'].add('validate')
        return result

    # No "Refuse" button on an approved request (Odoo's own automatic refusals,
    # e.g. a public holiday added later, still work); if plans change, the employee
    # cancels it, or HR sends it back to approval.
    def _compute_can_refuse(self):
        super()._compute_can_refuse()
        for holiday in self.filtered(lambda h: h.state == 'validate'):
            holiday.can_refuse = False

    def _compute_can_back_to_approve(self):
        super()._compute_can_back_to_approve()
        for holiday in self.filtered(lambda h: h.state == 'refuse'):
            holiday.can_back_to_approve = holiday._check_approval_update('confirm', raise_if_not_possible=False)

    def _check_double_validation_rules(self, employees, state):
        # the first approval of a double-validation request: any equal head may give it
        if state == 'validate1':
            user = self.env.user
            employees = employees.filtered(lambda e: user not in e.sudo().sh_head_user_ids)
        return super()._check_double_validation_rules(employees, state)

    def _get_responsible_for_approval(self):
        responsible = super()._get_responsible_for_approval()
        if self.validation_type == 'manager' or (self.validation_type == 'both' and self.state == 'confirm'):
            employee = self.employee_id.sudo()
            heads = employee.sh_head_user_ids
            if employee.leave_manager_id in heads:
                responsible |= heads
        return responsible

    @api.model
    def sh_waiting_for_me_count(self):
        """Requests waiting for the current user's approval - same rule as Odoo's
        "Waiting For Me" filter. -1 when the user approves nothing."""
        user = self.env.user
        if user.has_group('hr_holidays.group_hr_holidays_user'):
            domain = [('state', 'in', ['confirm', 'validate1']), '|', ('employee_id.user_id', '!=', user.id),
                      '|', '&', ('state', '=', 'confirm'), ('holiday_status_id.leave_validation_type', '=', 'hr'),
                      ('state', '=', 'validate1')]
        elif user.has_group('hr_holidays.group_hr_holidays_responsible') or                 self.env['hr.employee'].sudo().search_count([('sh_head_user_ids', 'in', [user.id])]):
            domain = [('state', '=', 'confirm'), ('validation_type', '!=', 'hr'),
                      '|', ('employee_id.leave_manager_id', '=', user.id),
                      ('employee_id.sh_head_user_ids', 'in', [user.id]),
                      ('employee_id.user_id', '!=', user.id)]
        else:
            return -1
        return self.search_count(domain)

    delegation_ids = fields.One2many(
        'steelhouse.leave.delegation', 'leave_id', string='შემცვლელები', copy=False,
        help="ვინ ჩაიბარებს თითოეული დეპარტამენტის საკითხებს შვებულების დროს.")

    @api.onchange('employee_id')
    def _onchange_employee_prefill_delegations(self):
        """Prefill deputies: a department head gets one line per managed department
        (with that department's deputy); others get one line for their own department."""
        for leave in self:
            if leave.delegation_ids or not leave.employee_id:
                continue
            employee = leave.employee_id
            managed = self.env['hr.department'].search(['|', ('manager_id', '=', employee.id), ('manager_ids', 'in', employee.id)])
            if managed:
                lines = [{'department_id': d.id, 'deputy_id': d.deputy_id.id if d.deputy_id != employee else False}
                         for d in managed]
            elif employee.department_id:
                lines = [{'department_id': employee.department_id.id}]
            else:
                lines = []
            leave.delegation_ids = [(0, 0, vals) for vals in lines]

    @api.constrains('date_from', 'date_to')
    def _check_deputies_available(self):
        """New dates of a request: its deputies must not be on leave themselves then."""
        self.delegation_ids._check_deputy_available()

    def _drop_empty_delegations(self):
        self.delegation_ids.filtered(lambda l: not l.deputy_id).unlink()

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves._drop_empty_delegations()
        return leaves

    def write(self, vals):
        res = super().write(vals)
        if 'delegation_ids' in vals:
            self._drop_empty_delegations()
        return res

    # ------------------------------------------------------------------
    # Notify deputies (inbox notification; email too once SMTP is set up)
    # ------------------------------------------------------------------
    def _steelhouse_notify_deputies(self, event):
        titles = {
            'approved': _("თქვენ ხართ შემცვლელი შვებულების დროს"),
            'cancelled': _("შვებულება გაუქმდა — შემცვლელობა აღარ არის საჭირო"),
        }
        for leave in self:
            period = "%s – %s" % (
                leave.request_date_from and leave.request_date_from.strftime('%d/%m/%Y') or '',
                leave.request_date_to and leave.request_date_to.strftime('%d/%m/%Y') or '')
            by_partner = {}
            for line in leave.delegation_ids.filtered(lambda l: l.deputy_id.user_id):
                by_partner.setdefault(line.deputy_id.user_id.partner_id, []).append(line.department_id.display_name)
            for partner, departments in by_partner.items():
                if event == 'approved':
                    text = _("%(employee)s შვებულებაში იქნება %(period)s. თქვენ ხართ მისი შემცვლელი: %(departments)s.",
                             employee=leave.employee_id.name, period=period, departments=", ".join(departments))
                else:
                    text = _("%(employee)s-ის შვებულება (%(period)s) გაუქმდა. შემცვლელობა (%(departments)s) აღარ არის საჭირო.",
                             employee=leave.employee_id.name, period=period, departments=", ".join(departments))
                leave.message_notify(
                    partner_ids=partner.ids,
                    subject=titles[event],
                    body=Markup("<p>%s</p>") % text,
                )
                # users get notifications by e-mail and there is no mail server yet:
                # the same text also goes to the deputy's Odoo chat (from OdooBot)
                leave._steelhouse_chat(partner, Markup("<p><b>%s</b></p><p>%s</p>") % (titles[event], text))

    def _steelhouse_chat(self, partner, body):
        bot = self.env.ref('base.user_root')
        Channel = self.env['discuss.channel'].with_user(bot).sudo()
        channel = Channel._get_or_create_chat([partner.id], pin=True)
        if isinstance(channel, dict):
            channel = Channel.browse(channel['id'])
        channel.message_post(body=body, author_id=bot.partner_id.id,
                             message_type='comment', subtype_xmlid='mail.mt_comment')

    def _action_validate(self, check_state=True):
        res = super()._action_validate(check_state=check_state)
        self.filtered(lambda l: l.state == 'validate')._steelhouse_notify_deputies('approved')
        return res

    def action_refuse(self):
        was_approved = self.filtered(lambda l: l.state == 'validate')
        res = super().action_refuse()
        was_approved.filtered(lambda l: l.state != 'validate')._steelhouse_notify_deputies('cancelled')
        return res

    def _force_cancel(self, *args, **kwargs):
        was_approved = self.filtered(lambda l: l.state == 'validate')
        res = super()._force_cancel(*args, **kwargs)
        was_approved.filtered(lambda l: l.state != 'validate')._steelhouse_notify_deputies('cancelled')
        return res
