"""HR's time off report (Docs/HR "შვებულების პროცესი", 2026-11-20): approved paid and unpaid time off
per employee and month, and the totals of the period - in Excel, PDF and on screen (pivot).

A request spanning several months is split by its days: unpaid leave ("კალენდარული დღეებით") counts
every calendar day, other types count the employee's working days (public holidays excluded); half
days keep the request's own total (its days are scaled to number_of_days)."""
import base64
import io
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

MONTHS = ['იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი', 'ივლისი', 'აგვისტო',
          'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი']
KINDS = [('paid', 'ანაზღაურებადი'), ('unpaid', 'ანაზღაურების გარეშე')]


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    sh_report_kind = fields.Selection(
        KINDS, string='HR-ის რეპორტში',
        help="რომელ სვეტში ჩაითვლება ამ ტიპის შვებულება თვეების რეპორტში (ცარიელი - არ ჩაითვლება).")


class ShLeaveReportWizard(models.TransientModel):
    _name = 'sh.leave.report.wizard'
    _description = 'შვებულების რეპორტი თვეების მიხედვით'

    date_from = fields.Date('დან', required=True, default=lambda self: date(fields.Date.today().year, 1, 1))
    date_to = fields.Date('მდე', required=True, default=lambda self: date(fields.Date.today().year, 12, 31))
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი',
                                    help="ცარიელი - ყველა; არჩეული - ის და მისი ქვედეპარტამენტები.")
    employee_ids = fields.Many2many('hr.employee', string='თანამშრომლები', help="ცარიელი - ყველა.")
    only_with_leave = fields.Boolean('მხოლოდ ვისაც შვებულება ჰქონდა', default=True)

    # ------------------------------------------------------------------ data
    def _sh_months(self):
        self.ensure_one()
        first = self.date_from.replace(day=1)
        months = []
        while first <= self.date_to:
            months.append(first)
            first += relativedelta(months=1)
        return months

    def _sh_employees(self):
        domain = []
        if self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        if self.department_id:
            domain.append(('department_id', 'child_of', self.department_id.id))
        return self.env['hr.employee'].search(domain, order='name')

    @staticmethod
    def _sh_working_day(day, weekdays, holidays):
        return str(day.weekday()) in weekdays and day not in holidays

    def _sh_holidays(self, calendar, start, stop):
        """Public holidays (company-wide time off of a calendar or of all calendars)."""
        leaves = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False), ('date_from', '<=', fields.Datetime.to_datetime(stop) + timedelta(days=1)),
            ('date_to', '>=', fields.Datetime.to_datetime(start)),
            '|', ('calendar_id', '=', False), ('calendar_id', '=', calendar.id if calendar else False)])
        days = set()
        for leave in leaves:
            day = leave.date_from.date()
            while day <= leave.date_to.date():
                days.add(day)
                day += timedelta(days=1)
        return days

    def _sh_data(self):
        """{'months': [date], 'rows': [{employee, department, months: {date: {'paid','unpaid'}}, paid, unpaid,
        requests}], 'totals': {...}}"""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("„დან“ თარიღი „მდე“-ზე გვიან არის."))
        months = self._sh_months()
        employees = self._sh_employees()
        leaves = self.env['hr.leave'].search([
            ('employee_id', 'in', employees.ids), ('state', '=', 'validate'),
            ('holiday_status_id.sh_report_kind', '!=', False),
            ('request_date_from', '<=', self.date_to), ('request_date_to', '>=', self.date_from)])
        empty = lambda: {m: {'paid': 0.0, 'unpaid': 0.0} for m in months}
        rows = {e.id: {'employee': e.name, 'department': e.department_id.name or '', 'months': empty(),
                       'paid': 0.0, 'unpaid': 0.0, 'requests': 0} for e in employees}
        holiday_cache = {}
        for leave in leaves:
            kind = leave.holiday_status_id.sh_report_kind
            calendar = leave.resource_calendar_id or leave.employee_id.resource_calendar_id
            weekdays = set(calendar.attendance_ids.mapped('dayofweek')) if calendar else {'0', '1', '2', '3', '4'}
            key = calendar.id if calendar else 0
            if key not in holiday_cache:
                holiday_cache[key] = self._sh_holidays(calendar, self.date_from - timedelta(days=400),
                                                       self.date_to + timedelta(days=400))
            calendar_days = leave.holiday_status_id.sh_calendar_days
            counted = []
            day = leave.request_date_from
            while day <= leave.request_date_to:
                if calendar_days or self._sh_working_day(day, weekdays, holiday_cache[key]):
                    counted.append(day)
                day += timedelta(days=1)
            if not counted:
                continue
            weight = (leave.number_of_days or len(counted)) / len(counted)
            row = rows[leave.employee_id.id]
            row['requests'] += 1
            for day in counted:
                if self.date_from <= day <= self.date_to:
                    month = day.replace(day=1)
                    row['months'][month][kind] += weight
                    row[kind] += weight
        result = [r for r in rows.values() if not self.only_with_leave or r['paid'] or r['unpaid']]
        totals = {'months': empty(), 'paid': 0.0, 'unpaid': 0.0}
        for r in result:
            for m in months:
                for k in ('paid', 'unpaid'):
                    totals['months'][m][k] += r['months'][m][k]
            totals['paid'] += r['paid']
            totals['unpaid'] += r['unpaid']
        return {'months': months, 'rows': result, 'totals': totals,
                'period': '%s - %s' % (self.date_from.strftime('%d.%m.%Y'), self.date_to.strftime('%d.%m.%Y')),
                'department': self.department_id.name or 'ყველა დეპარტამენტი'}

    @staticmethod
    def sh_num(value):
        value = round(value or 0, 2)
        return ('%g' % value).replace('.', ',') if value else ''

    @staticmethod
    def sh_month_label(month):
        return '%s %s' % (MONTHS[month.month - 1], month.year)

    # ------------------------------------------------------------------ outputs
    def action_pdf(self):
        self.ensure_one()
        self._sh_data()   # checks the dates before the report opens
        return self.env.ref('steelhouse_hr.action_report_sh_leave_month').report_action(self)

    def action_excel(self):
        self.ensure_one()
        import xlsxwriter
        data = self._sh_data()
        buffer = io.BytesIO()
        book = xlsxwriter.Workbook(buffer, {'in_memory': True})
        bold = book.add_format({'bold': True})
        head = book.add_format({'bold': True, 'bg_color': '#EEEBF6', 'border': 1, 'text_wrap': True,
                                'align': 'center', 'valign': 'vcenter'})
        cell = book.add_format({'border': 1})
        num = book.add_format({'border': 1, 'num_format': '0.##'})
        total = book.add_format({'border': 1, 'bold': True, 'num_format': '0.##', 'bg_color': '#F6F4FB'})

        # sheet 1: by month
        sheet = book.add_worksheet('თვეების მიხედვით')
        sheet.write(0, 0, 'შვებულება თვეების მიხედვით: %s, %s' % (data['period'], data['department']), bold)
        sheet.merge_range(2, 0, 3, 0, 'თანამშრომელი', head)
        sheet.merge_range(2, 1, 3, 1, 'დეპარტამენტი', head)
        col = 2
        for month in data['months']:
            sheet.merge_range(2, col, 2, col + 1, self.sh_month_label(month), head)
            sheet.write(3, col, 'ანაზღ.', head)
            sheet.write(3, col + 1, 'უხელფ.', head)
            col += 2
        sheet.merge_range(2, col, 2, col + 1, 'სულ', head)
        sheet.write(3, col, 'ანაზღ.', head)
        sheet.write(3, col + 1, 'უხელფ.', head)
        row = 4
        for r in data['rows']:
            sheet.write(row, 0, r['employee'], cell)
            sheet.write(row, 1, r['department'], cell)
            c = 2
            for month in data['months']:
                for k in ('paid', 'unpaid'):
                    value = r['months'][month][k]
                    sheet.write(row, c, round(value, 2) if value else '', num)
                    c += 1
            sheet.write(row, c, round(r['paid'], 2), total)
            sheet.write(row, c + 1, round(r['unpaid'], 2), total)
            row += 1
        sheet.write(row, 0, 'სულ', total)
        sheet.write(row, 1, '', total)
        c = 2
        for month in data['months']:
            for k in ('paid', 'unpaid'):
                sheet.write(row, c, round(data['totals']['months'][month][k], 2), total)
                c += 1
        sheet.write(row, c, round(data['totals']['paid'], 2), total)
        sheet.write(row, c + 1, round(data['totals']['unpaid'], 2), total)
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 30)
        sheet.set_column(2, c + 1, 8)
        sheet.freeze_panes(4, 2)

        # sheet 2: totals of the period
        sheet = book.add_worksheet('ჯამი პერიოდში')
        sheet.write(0, 0, 'შვებულება ჯამურად: %s, %s' % (data['period'], data['department']), bold)
        for c, title in enumerate(['თანამშრომელი', 'დეპარტამენტი', 'ანაზღაურებადი (დღე)',
                                   'ანაზღაურების გარეშე (დღე)', 'სულ (დღე)', 'მოთხოვნები']):
            sheet.write(2, c, title, head)
        row = 3
        for r in data['rows']:
            sheet.write(row, 0, r['employee'], cell)
            sheet.write(row, 1, r['department'], cell)
            sheet.write(row, 2, round(r['paid'], 2), num)
            sheet.write(row, 3, round(r['unpaid'], 2), num)
            sheet.write(row, 4, round(r['paid'] + r['unpaid'], 2), total)
            sheet.write(row, 5, r['requests'], num)
            row += 1
        sheet.write(row, 0, 'სულ', total)
        sheet.write(row, 1, '', total)
        sheet.write(row, 2, round(data['totals']['paid'], 2), total)
        sheet.write(row, 3, round(data['totals']['unpaid'], 2), total)
        sheet.write(row, 4, round(data['totals']['paid'] + data['totals']['unpaid'], 2), total)
        sheet.set_column(0, 1, 30)
        sheet.set_column(2, 5, 16)
        book.close()

        name = 'შვებულება %s - %s.xlsx' % (self.date_from.strftime('%d.%m.%Y'), self.date_to.strftime('%d.%m.%Y'))
        attachment = self.env['ir.attachment'].create({
            'name': name, 'datas': base64.b64encode(buffer.getvalue()),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'self'}

    def action_view(self):
        """On screen: Odoo's time off analysis as a pivot - employees by month and type."""
        self.ensure_one()
        domain = [('leave_type', '=', 'request'), ('state', '=', 'validate'),
                  ('holiday_status_id.sh_report_kind', '!=', False),
                  ('date_from', '<=', fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)),
                  ('date_to', '>=', fields.Datetime.to_datetime(self.date_from))]
        employees = self._sh_employees() if (self.employee_ids or self.department_id) else False
        if employees is not False:
            domain.append(('employee_id', 'in', employees.ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('შვებულება თვეების მიხედვით'),
            'res_model': 'hr.leave.report',
            'views': [[False, 'pivot'], [False, 'list']],
            'domain': domain,
            'context': {'pivot_row_groupby': ['employee_id'],
                        'pivot_column_groupby': ['date_from:month', 'holiday_status_id'],
                        'pivot_measures': ['number_of_days']},
        }


class ReportShLeaveMonth(models.AbstractModel):
    _name = 'report.steelhouse_hr.report_sh_leave_month'
    _description = 'შვებულების რეპორტი თვეების მიხედვით (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizards = self.env['sh.leave.report.wizard'].browse(docids)
        return {'docs': wizards, 'wizard_data': {w.id: w._sh_data() for w in wizards},
                'num': ShLeaveReportWizard.sh_num, 'month_label': ShLeaveReportWizard.sh_month_label}
