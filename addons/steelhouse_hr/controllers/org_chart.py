from odoo import http
from odoo.http import request

from odoo.addons.hr_org_chart.controllers.hr_org_chart import HrOrgChartController


class SteelhouseOrgChart(HrOrgChartController):
    """Org chart that shows all equal heads of a department side by side."""

    def _sh_emp(self, public):
        return request.env['hr.employee'].sudo().browse(public.id)

    def _sh_public(self, employees):
        return request.env['hr.employee.public'].sudo().browse(employees.ids)

    def _prepare_employee_data(self, employee):
        data = super()._prepare_employee_data(employee)
        emp = self._sh_emp(employee)
        data['direct_sub_count'] = len(emp._sh_direct_reports())
        data['indirect_sub_count'] = len(emp._sh_all_reports())
        return data

    @http.route()
    def get_org_chart(self, employee_id, new_parent_id=None, **kw):
        values = super().get_org_chart(employee_id, new_parent_id=new_parent_id, **kw)
        if not values.get('self'):
            return values
        Emp = request.env['hr.employee'].sudo()
        chain = [m['id'] for m in values['managers']] + [values['self']['id']]
        for i, manager in enumerate(values['managers']):
            below = Emp.browse(chain[i + 1])
            if below.parent_id.id == manager['id']:
                co = below._sh_heads() - Emp.browse(manager['id'])
            else:
                co = Emp
            manager['co'] = [self._prepare_employee_data(p) for p in self._sh_public(co)]
        me = Emp.browse(values['self']['id'])
        values['children'] = [self._prepare_employee_data(p) for p in self._sh_public(me._sh_direct_reports())]
        return values

    @http.route()
    def get_subordinates(self, employee_id, subordinates_type=None, **kw):
        employee = self._get_employee(employee_id, **kw)
        if not employee:
            return {}
        emp = self._sh_emp(employee)
        direct, everyone = emp._sh_direct_reports(), emp._sh_all_reports()
        if subordinates_type == 'direct':
            return direct.ids
        if subordinates_type == 'indirect':
            return (everyone - direct).ids
        return everyone.ids
