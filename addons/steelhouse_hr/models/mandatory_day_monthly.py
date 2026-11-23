"""Mandatory working days that repeat every month (accounting: the 15th and the 16th, 2026-11-23).

Odoo's mandatory days are one-off date ranges. A record marked "ყოველთვე მეორდება" is a template: the
same days of the month are created as ordinary mandatory days for the next 12 months (a daily cron
keeps 12 months ahead), so every standard behaviour - the calendar, blocking the request, the time
off types that ignore mandatory days - works unchanged. Changing the template changes its future
copies; switching the repetition off removes them (past ones stay as history)."""
import calendar as pycal
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

MONTHS_AHEAD = 12
SYNCED = ('name', 'color', 'company_id', 'resource_calendar_id', 'department_ids', 'job_ids')


class HrLeaveMandatoryDay(models.Model):
    _inherit = 'hr.leave.mandatory.day'

    sh_repeat_monthly = fields.Boolean(
        string='ყოველთვე მეორდება',
        help="იგივე რიცხვები (მაგ. 15-16) ყოველ თვეს სავალდებულო დღედ შეიქმნება - წინასწარ 12 თვეზე.")
    sh_template_id = fields.Many2one(
        'hr.leave.mandatory.day', string='ყოველთვიური ჩანაწერიდან', readonly=True, index=True, ondelete='cascade')

    @api.model
    def _sh_month_dates(self, template, month):
        last = pycal.monthrange(month.year, month.month)[1]
        start = date(month.year, month.month, min(template.start_date.day, last))
        end = date(month.year, month.month, min(template.end_date.day, last))
        return start, max(start, end)

    def _sh_values(self):
        self.ensure_one()
        return {
            'name': self.name, 'color': self.color, 'company_id': self.company_id.id,
            'resource_calendar_id': self.resource_calendar_id.id,
            'department_ids': [(6, 0, self.department_ids.ids)], 'job_ids': [(6, 0, self.job_ids.ids)],
        }

    @api.model
    def _sh_generate_monthly(self, today=None):
        """Daily: every repeating template gets its days in each of the next 12 months."""
        today = today or fields.Date.context_today(self)
        templates = self.sudo().search([('sh_repeat_monthly', '=', True), ('sh_template_id', '=', False)])
        for template in templates:
            if not template.start_date or not template.end_date:
                continue
            existing = set(self.sudo().search([('sh_template_id', '=', template.id)]).mapped('start_date'))
            month = template.start_date.replace(day=1) + relativedelta(months=1)
            stop = today.replace(day=1) + relativedelta(months=MONTHS_AHEAD)
            values = template._sh_values()
            while month <= stop:
                start, end = self._sh_month_dates(template, month)
                if start not in existing and end >= today:
                    self.sudo().create(dict(values, start_date=start, end_date=end, sh_template_id=template.id))
                month += relativedelta(months=1)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records.filtered('sh_repeat_monthly'):
            self._sh_generate_monthly()
        return records

    def write(self, vals):
        res = super().write(vals)
        templates = self.filtered(lambda r: not r.sh_template_id)
        if not templates or self.env.context.get('sh_mandatory_sync'):
            return res
        today = fields.Date.context_today(self)
        future = self.sudo().search([('sh_template_id', 'in', templates.ids), ('start_date', '>=', today)])
        if 'sh_repeat_monthly' in vals and not vals['sh_repeat_monthly']:
            future.unlink()
        elif any(f in vals for f in SYNCED) or 'start_date' in vals or 'end_date' in vals:
            # days of the month changed: the future copies are made again; other fields are copied over
            if 'start_date' in vals or 'end_date' in vals:
                future.unlink()
            else:
                for template in templates:
                    future.filtered(lambda c: c.sh_template_id == template).with_context(
                        sh_mandatory_sync=True).write(template._sh_values())
            self._sh_generate_monthly()
        elif vals.get('sh_repeat_monthly'):
            self._sh_generate_monthly()
        return res
