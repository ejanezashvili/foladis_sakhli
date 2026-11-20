"""HR's time off report page ("შვებულება → რეპორტინგი → შვებულების რეპორტი", static/src/leave_report):
filters (period, department, employee, statuses), three cuts - by month (paid / unpaid / other per month),
by type, by status - rows by employee or by department, each row opens its requests; Excel and PDF of
exactly what is on the screen.

Days are counted inside the period: a request spanning several months is split by its days (unpaid -
"კალენდარული დღეებით" - every calendar day, other types the employee's working days without public
holidays; the request's own total is kept, so half days stay right)."""
import base64
import io
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MONTHS = ['იანვარი', 'თებერვალი', 'მარტი', 'აპრილი', 'მაისი', 'ივნისი', 'ივლისი', 'აგვისტო',
          'სექტემბერი', 'ოქტომბერი', 'ნოემბერი', 'დეკემბერი']
KINDS = [('paid', 'ანაზღაურებადი'), ('unpaid', 'ანაზღაურების გარეშე')]
KIND_SHORT = {'paid': 'ანაზღ.', 'unpaid': 'უხელფ.', 'other': 'სხვა'}
STATES = [('validate', 'დამტკიცებული'), ('waiting', 'დასამტკიცებელი'), ('refuse', 'უარყოფილი'),
          ('cancel', 'გაუქმებული')]
STATE_OF = {'validate': 'validate', 'confirm': 'waiting', 'validate1': 'waiting', 'refuse': 'refuse',
            'cancel': 'cancel'}
VIEWS = {'month': 'თვეების მიხედვით', 'type': 'ტიპების მიხედვით', 'state': 'სტატუსების მიხედვით'}


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    sh_report_kind = fields.Selection(
        KINDS, string='HR-ის რეპორტში',
        help="თვეების რეპორტში რომელ სვეტშია ეს ტიპი: ანაზღაურებადი / ანაზღაურების გარეშე (ცარიელი - „სხვა“).")


def _num(value):
    value = round(value or 0, 2)
    return ('%g' % value).replace('.', ',') if value else ''


class ShLeaveReport(models.AbstractModel):
    _name = 'sh.leave.report'
    _description = 'შვებულების რეპორტი'

    # ------------------------------------------------------------------ helpers
    def _sh_check(self):
        if not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            raise AccessError(_("შვებულების რეპორტი ხელმისაწვდომია მხოლოდ HR-ისთვის."))

    @api.model
    def _sh_params(self, params):
        params = dict(params or {})
        today = fields.Date.context_today(self)
        date_from = fields.Date.to_date(params.get('date_from')) or date(today.year, 1, 1)
        date_to = fields.Date.to_date(params.get('date_to')) or date(today.year, 12, 31)
        if date_from > date_to:
            raise UserError(_("„დან“ თარიღი „მდე“-ზე გვიან არის."))
        states = [s for s in (params.get('states') or ['validate']) if s in dict(STATES)] or ['validate']
        return {
            'date_from': date_from, 'date_to': date_to,
            'department_id': int(params.get('department_id') or 0),
            'employee_id': int(params.get('employee_id') or 0),
            'states': states,
            'view': params.get('view') if params.get('view') in VIEWS else 'month',
            'group': 'department' if params.get('group') == 'department' else 'employee',
        }

    @api.model
    def _sh_holidays(self, calendar, start, stop):
        leaves = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('date_from', '<=', fields.Datetime.to_datetime(stop) + timedelta(days=1)),
            ('date_to', '>=', fields.Datetime.to_datetime(start)),
            '|', ('calendar_id', '=', False), ('calendar_id', '=', calendar.id if calendar else False)])
        days = set()
        for leave in leaves:
            day = leave.date_from.date()
            while day <= leave.date_to.date():
                days.add(day)
                day += timedelta(days=1)
        return days

    @api.model
    def _sh_leave_days(self, leave, cache):
        """{day: weight} of a request: its counted days, weighted so they add up to its own total."""
        calendar = leave.resource_calendar_id or leave.employee_id.resource_calendar_id
        key = calendar.id if calendar else 0
        if key not in cache:
            cache[key] = (set(calendar.attendance_ids.mapped('dayofweek')) if calendar else {'0', '1', '2', '3', '4'},
                          self._sh_holidays(calendar, leave.request_date_from - timedelta(days=400),
                                            leave.request_date_to + timedelta(days=400)))
        weekdays, holidays = cache[key]
        every_day = leave.holiday_status_id.sh_calendar_days
        counted = []
        day = leave.request_date_from
        while day <= leave.request_date_to:
            if every_day or (str(day.weekday()) in weekdays and day not in holidays):
                counted.append(day)
            day += timedelta(days=1)
        if not counted:
            return {}
        weight = (leave.number_of_days or len(counted)) / len(counted)
        return {day: weight for day in counted}

    # ------------------------------------------------------------------ data
    @api.model
    def sh_lists(self):
        self._sh_check()
        # complete_name is not stored here (steelhouse_hr computes it) - sort in Python
        depts = self.env['hr.department'].search([])
        names = sorted(((d.id, (d.complete_name or d.name or '').replace('ფოლადის სახლი / ', '')) for d in depts),
                       key=lambda x: x[1])
        emps = self.env['hr.employee'].search([], order='name')
        return {
            'departments': [{'id': i, 'name': n} for i, n in names],
            'employees': [{'id': e.id, 'name': e.name, 'department_id': e.department_id.id} for e in emps],
            'states': [{'key': k, 'label': v} for k, v in STATES],
            'views': [{'key': k, 'label': v} for k, v in VIEWS.items()],
        }

    @api.model
    def sh_report_data(self, params=None):
        self._sh_check()
        p = self._sh_params(params)
        date_from, date_to = p['date_from'], p['date_to']
        state_values = [s for s, k in STATE_OF.items() if k in p['states']]
        domain = [('state', 'in', state_values),
                  ('request_date_from', '<=', date_to), ('request_date_to', '>=', date_from)]
        if p['employee_id']:
            domain.append(('employee_id', '=', p['employee_id']))
        if p['department_id']:
            domain.append(('employee_id.department_id', 'child_of', p['department_id']))
        leaves = self.env['hr.leave'].search(domain, order='request_date_from')

        months = []
        month = date_from.replace(day=1)
        while month <= date_to:
            months.append(month)
            month += relativedelta(months=1)

        cache = {}
        rows, totals = {}, {}
        kinds_used, types_used = set(), {}
        kpi = {'days': 0.0, 'paid': 0.0, 'unpaid': 0.0, 'other': 0.0}
        employees_used = set()
        for leave in leaves:
            days = {d: w for d, w in self._sh_leave_days(leave, cache).items() if date_from <= d <= date_to}
            if not days:
                continue
            kind = leave.holiday_status_id.sh_report_kind or 'other'
            state = STATE_OF.get(leave.state, leave.state)
            in_period = sum(days.values())
            employee = leave.employee_id
            if p['group'] == 'department':
                key, label, sub = employee.department_id.id or 0, employee.department_id.name or 'დეპარტამენტის გარეშე', ''
            else:
                key, label, sub = employee.id, employee.name, employee.department_id.name or ''
            row = rows.setdefault(key, {'key': key, 'label': label, 'sub': sub, 'values': {}, 'total': 0.0,
                                        'items': []})
            cells = {}
            if p['view'] == 'month':
                kinds_used.add(kind)
                for day, weight in days.items():
                    col = '%s|%s' % (day.strftime('%Y-%m'), kind)
                    cells[col] = cells.get(col, 0.0) + weight
            elif p['view'] == 'type':
                types_used[leave.holiday_status_id.id] = leave.holiday_status_id.name
                cells['t%s' % leave.holiday_status_id.id] = in_period
            else:
                cells[state] = in_period
            for col, value in cells.items():
                row['values'][col] = row['values'].get(col, 0.0) + value
                totals[col] = totals.get(col, 0.0) + value
            row['total'] += in_period
            if state == 'validate':
                kpi['days'] += in_period
                kpi[kind] += in_period
            employees_used.add(employee.id)
            row['items'].append({
                'id': leave.id,
                'employee': employee.name,
                'type': leave.holiday_status_id.name,
                'dates': '%s - %s' % (leave.request_date_from.strftime('%d.%m.%Y'),
                                      leave.request_date_to.strftime('%d.%m.%Y')),
                'days': round(in_period, 2),
                'state': dict(STATES).get(state, state),
                'state_key': state,
                'approvers': ', '.join(n for n in (leave.first_approver_id.name, leave.second_approver_id.name) if n),
            })

        # columns
        groups, columns = [], []
        if p['view'] == 'month':
            kinds = [k for k in ('paid', 'unpaid', 'other') if k in kinds_used] or ['paid', 'unpaid']
            for month in months:
                cols = [{'key': '%s|%s' % (month.strftime('%Y-%m'), k), 'label': KIND_SHORT[k]} for k in kinds]
                groups.append({'label': '%s %s' % (MONTHS[month.month - 1], month.year), 'span': len(cols)})
                columns += cols
        elif p['view'] == 'type':
            columns = [{'key': 't%s' % tid, 'label': name} for tid, name in sorted(types_used.items(), key=lambda x: x[1])]
        else:
            columns = [{'key': k, 'label': dict(STATES)[k]} for k in [s for s, _l in STATES if s in p['states']]]

        result_rows = sorted(rows.values(), key=lambda r: (r['label'] or ''))
        for row in result_rows:
            row['values'] = {k: round(v, 2) for k, v in row['values'].items()}
            row['total'] = round(row['total'], 2)
        return {
            'params': {**p, 'date_from': date_from.isoformat(), 'date_to': date_to.isoformat()},
            'period': '%s - %s' % (date_from.strftime('%d.%m.%Y'), date_to.strftime('%d.%m.%Y')),
            'view_label': VIEWS[p['view']],
            'filter_label': self._sh_filter_label(p),
            'groups': groups,
            'columns': columns,
            'rows': result_rows,
            'totals': {k: round(v, 2) for k, v in totals.items()},
            'total': round(sum(r['total'] for r in result_rows), 2),
            'kpi': {'days': round(kpi['days'], 2), 'paid': round(kpi['paid'], 2), 'unpaid': round(kpi['unpaid'], 2),
                    'employees': len(employees_used), 'requests': sum(len(r['items']) for r in result_rows)},
            'group_label': 'დეპარტამენტი' if p['group'] == 'department' else 'თანამშრომელი',
        }

    def _sh_filter_label(self, p):
        parts = []
        if p['department_id']:
            parts.append(self.env['hr.department'].browse(p['department_id']).name)
        if p['employee_id']:
            parts.append(self.env['hr.employee'].browse(p['employee_id']).name)
        parts.append(', '.join(dict(STATES)[s] for s in p['states']))
        return ' · '.join(parts)

    # ------------------------------------------------------------------ exports
    @api.model
    def sh_report_pdf(self, params=None):
        self._sh_check()
        self._sh_params(params)
        return self.env.ref('steelhouse_hr.action_report_sh_leave').report_action(None, data={'params': params or {}})

    @api.model
    def sh_report_excel(self, params=None):
        import xlsxwriter
        data = self.sh_report_data(params)
        buffer = io.BytesIO()
        book = xlsxwriter.Workbook(buffer, {'in_memory': True})
        title = book.add_format({'bold': True, 'font_size': 13})
        muted = book.add_format({'font_color': '#7a7790'})
        head = book.add_format({'bold': True, 'bg_color': '#EEEBF6', 'border': 1, 'text_wrap': True,
                                'align': 'center', 'valign': 'vcenter'})
        cell = book.add_format({'border': 1})
        num = book.add_format({'border': 1, 'num_format': '0.##'})
        total = book.add_format({'border': 1, 'bold': True, 'num_format': '0.##', 'bg_color': '#F6F4FB'})

        sheet = book.add_worksheet(data['view_label'][:31])
        sheet.write(0, 0, 'შვებულების რეპორტი - %s' % data['view_label'], title)
        sheet.write(1, 0, '%s · %s' % (data['period'], data['filter_label']), muted)
        row = 3
        first_col = 2 if data['params']['group'] == 'employee' else 1
        if data['groups']:
            sheet.merge_range(row, 0, row + 1, 0, data['group_label'], head)
            if first_col == 2:
                sheet.merge_range(row, 1, row + 1, 1, 'დეპარტამენტი', head)
            col = first_col
            for group in data['groups']:
                if group['span'] > 1:
                    sheet.merge_range(row, col, row, col + group['span'] - 1, group['label'], head)
                else:
                    sheet.write(row, col, group['label'], head)
                col += group['span']
            for i, column in enumerate(data['columns']):
                sheet.write(row + 1, first_col + i, column['label'], head)
            sheet.merge_range(row, first_col + len(data['columns']), row + 1, first_col + len(data['columns']), 'სულ', head)
            row += 2
        else:
            sheet.write(row, 0, data['group_label'], head)
            if first_col == 2:
                sheet.write(row, 1, 'დეპარტამენტი', head)
            for i, column in enumerate(data['columns']):
                sheet.write(row, first_col + i, column['label'], head)
            sheet.write(row, first_col + len(data['columns']), 'სულ', head)
            row += 1
        for r in data['rows']:
            sheet.write(row, 0, r['label'], cell)
            if first_col == 2:
                sheet.write(row, 1, r['sub'], cell)
            for i, column in enumerate(data['columns']):
                value = r['values'].get(column['key'])
                sheet.write(row, first_col + i, value or '', num)
            sheet.write(row, first_col + len(data['columns']), r['total'], total)
            row += 1
        sheet.write(row, 0, 'სულ', total)
        if first_col == 2:
            sheet.write(row, 1, '', total)
        for i, column in enumerate(data['columns']):
            sheet.write(row, first_col + i, data['totals'].get(column['key']) or '', total)
        sheet.write(row, first_col + len(data['columns']), data['total'], total)
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 26 if first_col == 2 else 9)
        sheet.set_column(first_col, first_col + len(data['columns']), 9 if data['groups'] else 16)
        sheet.freeze_panes(row - len(data['rows']), first_col)

        # every request
        sheet = book.add_worksheet('მოთხოვნები')
        titles = ['თანამშრომელი', 'ტიპი', 'თარიღები', 'დღე (პერიოდში)', 'სტატუსი', 'დაამტკიცა']
        for i, t in enumerate(titles):
            sheet.write(0, i, t, head)
        line = 1
        for r in data['rows']:
            for item in r['items']:
                for i, key in enumerate(('employee', 'type', 'dates', 'days', 'state', 'approvers')):
                    sheet.write(line, i, item[key], num if key == 'days' else cell)
                line += 1
        sheet.set_column(0, 1, 28)
        sheet.set_column(2, 2, 24)
        sheet.set_column(3, 4, 15)
        sheet.set_column(5, 5, 34)
        book.close()

        name = 'შვებულება - %s - %s.xlsx' % (data['view_label'], data['period'])
        attachment = self.env['ir.attachment'].create({
            'name': name, 'datas': base64.b64encode(buffer.getvalue()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}


class ReportShLeave(models.AbstractModel):
    _name = 'report.steelhouse_hr.report_sh_leave'
    _description = 'შვებულების რეპორტი (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['sh.leave.report'].sh_report_data((data or {}).get('params'))
        return {'d': report, 'num': _num}
