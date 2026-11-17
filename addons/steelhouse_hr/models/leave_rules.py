"""Company time off rules (Steel House):

- a time off type can be counted in calendar days (weekends and public holidays included),
  e.g. unpaid leave; paid leave keeps Odoo's working-day count;
- a time off type can ignore mandatory working days (sick leave, business trip);
- quarterly days: a type gives N days for every 3 months counted from each employee's own
  start date; unused days are lost when the quarter ends (the allocation expires).
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    sh_calendar_days = fields.Boolean(
        string='კალენდარული დღეებით',
        help="ხანგრძლივობა ითვლება კალენდარული დღეებით - შაბათ-კვირა და უქმეებიც შედის "
             "(მაგ. ანაზღაურების გარეშე შვებულება). გამორთულისას - სამუშაო დღეებით.")
    sh_ignore_mandatory_days = fields.Boolean(
        string='სავალდებულო დღეები არ ეხება',
        help="ამ ტიპის მოთხოვნა სავალდებულო სამუშაო დღეებზეც შეიძლება (მაგ. ავადმყოფობა, მივლინება).")
    sh_quarter_days = fields.Float(
        string='დღეები კვარტალში', digits=(16, 1),
        help="თუ მითითებულია: ყოველ თანამშრომელს, ვისაც „კვარტლის ათვლის თარიღი“ აქვს, ყოველ 3 თვეში "
             "ავტომატურად ეძლევა ამდენი დღე; კვარტლის ბოლოს გამოუყენებელი იწვის.")


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sh_quarter_start = fields.Date(
        string='შვებულების კვარტლის ათვლა', groups='hr.group_hr_user',
        help="თარიღი, საიდანაც თანამშრომელს შვებულების კვარტლები ეთვლება (ყოველი 3 თვე ამ დღიდან).")


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    sh_quarter_start = fields.Date(
        string='კვარტლის დასაწყისი', readonly=True, index=True, copy=False,
        help="ავტომატურად შექმნილი კვარტლის მინიჭება - რომელი კვარტლისაა.")

    @api.model
    def _sh_quarter_bounds(self, anchor, today):
        """The quarter (start, end) of `anchor`'s 3-month cycle that contains `today`."""
        if not anchor or anchor > today:
            return None, None
        start, step = anchor, 0
        while anchor + relativedelta(months=3 * (step + 1)) <= today:
            step += 1
        start = anchor + relativedelta(months=3 * step)
        end = anchor + relativedelta(months=3 * (step + 1)) - timedelta(days=1)
        return start, end

    @api.model
    def _sh_sync_quarter_allocations(self, today=None):
        """Daily: give every employee with a quarter start date the days of the current quarter
        for each time off type that has "days per quarter". Already created quarters are left as
        they are (their days can be corrected by hand, e.g. for the balance given by the company)."""
        today = today or fields.Date.context_today(self)
        types = self.env['hr.leave.type'].sudo().search([('sh_quarter_days', '>', 0)])
        if not types:
            return
        employees = self.env['hr.employee'].sudo().search([('sh_quarter_start', '!=', False)])
        Allocation = self.sudo()
        for leave_type in types:
            for employee in employees:
                if leave_type.company_id and employee.company_id != leave_type.company_id:
                    continue
                start, end = self._sh_quarter_bounds(employee.sh_quarter_start, today)
                if not start:
                    continue
                if Allocation.search_count([('employee_id', '=', employee.id),
                                            ('holiday_status_id', '=', leave_type.id),
                                            ('sh_quarter_start', '=', start)]):
                    continue
                allocation = Allocation.create({
                    'name': "%s - კვარტალი %s - %s" % (
                        leave_type.name, start.strftime('%d.%m.%Y'), end.strftime('%d.%m.%Y')),
                    'employee_id': employee.id,
                    'holiday_status_id': leave_type.id,
                    'allocation_type': 'regular',
                    'number_of_days': leave_type.sh_quarter_days,
                    'date_from': start,
                    'date_to': end,
                    'sh_quarter_start': start,
                })
                allocation._action_validate()


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _get_durations(self, check_leave_type=True, resource_calendar=None):
        result = super()._get_durations(check_leave_type=check_leave_type, resource_calendar=resource_calendar)
        for leave in self:
            if not (leave.holiday_status_id.sh_calendar_days and leave.request_date_from
                    and leave.request_date_to):
                continue
            # a few hours within one day stay as Odoo counts them
            if leave.request_unit_hours and leave.request_date_from == leave.request_date_to:
                continue
            days = (leave.request_date_to - leave.request_date_from).days + 1
            if leave.request_unit_half:
                if leave.request_date_from_period == 'pm':
                    days -= 0.5
                if leave.request_date_to_period == 'am':
                    days -= 0.5
            days = max(0, days)
            calendar = resource_calendar or leave.resource_calendar_id
            hours_per_day = (calendar.hours_per_day if calendar else 0) or 8
            result[leave.id] = (days, days * hours_per_day)
        return result

    @api.depends('date_from', 'date_to', 'holiday_status_id')
    def _compute_has_mandatory_day(self):
        super()._compute_has_mandatory_day()
        for leave in self:
            if leave.holiday_status_id.sh_ignore_mandatory_days:
                leave.has_mandatory_day = False
