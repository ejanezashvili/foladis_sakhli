"""7.10 PDF of the report screens ("ვადების დაცვა", "შეჩერება და გაუქმება", "სამუშაო დრო",
"დაბრუნებები"): the same rows as their Excel file, printed as a landscape A4 table.
The page sends plain texts only; they are cleaned here and printed escaped (t-esc)."""
from odoo import api, models

MAX_SECTIONS = 10
MAX_COLS = 20
MAX_ROWS = 5000


def _txt(value, size=300):
    return ('' if value is None else str(value))[:size]


def _clean(data):
    data = data or {}
    sections = []
    rows_left = MAX_ROWS
    for section in (data.get('sections') or [])[:MAX_SECTIONS]:
        if not isinstance(section, dict):
            continue
        head = [_txt(h, 120) for h in (section.get('head') or [])[:MAX_COLS]]
        rows = []
        for row in (section.get('rows') or [])[:rows_left]:
            if not isinstance(row, dict):
                continue
            cells = [_txt(c) for c in (row.get('cells') or [])[:MAX_COLS]]
            cells += [''] * (len(head) - len(cells))
            rows.append({'cells': cells, 'bold': bool(row.get('bold')), 'sub': bool(row.get('sub'))})
        rows_left -= len(rows)
        sections.append({'head': head, 'rows': rows})
    return {'title': _txt(data.get('title'), 200), 'subtitle': _txt(data.get('subtitle'), 300), 'sections': sections}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    @api.model
    def sh_table_pdf(self, data):
        """data: {title, subtitle, sections: [{head: [..], rows: [{cells: [..], bold, sub}]}]}"""
        return self.env.ref('steelhouse_task_flow.action_report_sh_table').report_action(None, data=_clean(data))


class ReportShTable(models.AbstractModel):
    _name = 'report.steelhouse_task_flow.report_sh_table'
    _description = 'რეპორტის ცხრილი (PDF)'

    @api.model
    def _get_report_values(self, docids, data=None):
        return {'t': _clean(data)}
