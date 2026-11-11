from datetime import datetime, time

from pytz import UTC

from odoo import api, fields, models
from odoo.fields import Domain


def _team_domain(employees, operator, value):
    """Domain for the 'My Team' filter: (not) in the current user's team."""
    positive = bool(value[0] if isinstance(value, (list, tuple)) and value else value)
    if operator in ('!=', 'not in'):
        positive = not positive
    return [('id', 'in' if positive else 'not in', employees._sh_my_team_ids())]


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sh_manager_ids = fields.Many2many(
        'hr.employee', compute='_compute_sh_manager_ids', string='ხელმძღვანელი',
        help="ყველა თანაბარი ხელმძღვანელი (დეპარტამენტის ხელმძღვანელებიდან).")
    sh_co_manager_ids = fields.Many2many(
        'hr.employee', compute='_compute_sh_manager_ids', string='სხვა თანაბარი ხელმძღვანელები')
    sh_my_team = fields.Boolean(compute='_compute_sh_my_team', search='_search_sh_my_team', string='ჩემი გუნდი')
    sh_under_me = fields.Boolean(
        compute='_compute_sh_under_me', search='_search_sh_under_me', string='ჩემ ქვეშ',
        help="ყველა, ვინც მიმდინარე მომხმარებლის ქვეშაა (ყველა დონე, ყველა თანაბარი ხელმძღვანელისთვის).")
    sh_extra_job_ids = fields.Many2many(
        'hr.job', 'hr_employee_sh_extra_job_rel', 'employee_id', 'job_id', string='დამატებითი პოზიციები',
        help="სხვა დეპარტამენტის პოზიციები, რომლებსაც თანამშრომელი ძირითადი პოზიციის გარდა იკავებს.")

    @api.model
    def _search_display_name(self, operator, value):
        """With context sh_search_department, typing a department name also finds its people."""
        domain = super()._search_display_name(operator, value)
        if self.env.context.get('sh_search_department') and isinstance(value, str) and value                 and operator in ('ilike', 'like', '=ilike'):
            domain = Domain.OR([domain, Domain('department_id.name', operator, value)])
        return domain

    # Direct manager (parent_id) follows the structure: the first head of the nearest unit
    # (own unit, then the units above it) that has a head other than the employee.
    def _sh_structure_manager(self):
        self.ensure_one()
        me = self._origin or self  # in a form, self is a draft copy of the record
        dept = self.department_id
        while dept and (not dept.manager_ids or me in dept.manager_ids):
            dept = dept.parent_id
        if not dept:
            return self.browse()
        return dept.manager_id if dept.manager_id in dept.manager_ids else dept.manager_ids[:1]

    def _sh_set_structure_manager(self):
        for emp in self.sudo():
            boss = emp._sh_structure_manager()
            if emp.parent_id != boss:
                super(HrEmployee, emp).write({'parent_id': boss.id})

    @api.onchange('department_id')
    def _onchange_sh_department_manager(self):
        for emp in self:
            if emp.department_id:
                emp.parent_id = emp._sh_structure_manager()

    @api.onchange('job_id')
    def _onchange_sh_job_department(self):
        """Choosing a position of a sub-unit moves the employee to that sub-unit."""
        for emp in self:
            job_dept = emp.job_id.department_id
            dept = emp.department_id
            inside = not dept or (job_dept.parent_path or '').startswith(dept.parent_path or '-')
            if job_dept and job_dept != dept and inside:
                emp.department_id = job_dept
                emp.parent_id = emp._sh_structure_manager()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        # manager from the structure, unless one was given explicitly
        auto = self.browse([emp.id for emp, vals in zip(employees, vals_list)
                            if emp.department_id and not vals.get('parent_id')])
        auto._sh_set_structure_manager()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'department_id' in vals and 'parent_id' not in vals:
            self._sh_set_structure_manager()
        return res

    def _get_unusual_days(self, date_from, date_to=None):
        """Weekends and public holidays in the time off calendar. Odoo takes them only from a
        contract with a start date; our employees have no contract data, so their work schedule
        (or the company's) is used instead."""
        if self and self.env['hr.version'].sudo().search_count(
                [('employee_id', '=', self.id), ('contract_date_start', '!=', False)]):
            return super()._get_unusual_days(date_from, date_to)
        company = self.company_id or self.env.company
        calendar = self.resource_calendar_id or company.resource_calendar_id
        start = datetime.strptime(date_from, '%Y-%m-%d %H:%M:%S').date()
        end = datetime.strptime(date_to, '%Y-%m-%d %H:%M:%S').date() if date_to else start
        return calendar.sudo()._get_unusual_days(
            datetime.combine(start, time.min).replace(tzinfo=UTC),
            datetime.combine(end, time.max).replace(tzinfo=UTC), company)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        """Deputy on a time off request (context sh_deputy_department_id): people of that
        department (and its sub-units) come first; any employee can still be found by typing."""
        dept_id = self.env.context.get('sh_deputy_department_id')
        if not dept_id:
            return super().name_search(name, domain, operator, limit)
        members = self.search(Domain.AND([domain or [], [('department_id', 'child_of', dept_id)]]),
                              order='name')
        if name:
            found = super().name_search(name, domain, operator, limit)
            first = [r for r in found if r[0] in members.ids]
            return first + [r for r in found if r[0] not in members.ids]
        result = [(e.id, e.display_name) for e in members[:limit]]
        if limit and len(result) < limit:
            others = super().name_search('', Domain.AND([domain or [], [('id', 'not in', members.ids)]]),
                                         operator, limit - len(result))
            result += others
        return result

    def _sh_under_me_ids(self):
        ids = set()
        for me in self.env.user.employee_ids.sudo():
            ids.update(me._sh_all_reports().ids)
        return list(ids)

    def _compute_sh_under_me(self):
        under = set(self._sh_under_me_ids())
        for emp in self:
            emp.sh_under_me = emp.id in under

    def _search_sh_under_me(self, operator, value):
        positive = bool(value[0] if isinstance(value, (list, tuple)) and value else value)
        if operator in ('!=', 'not in'):
            positive = not positive
        return [('id', 'in' if positive else 'not in', self._sh_under_me_ids())]

    def _compute_sh_my_team(self):
        team = self.env['hr.employee'].browse(self._sh_my_team_ids())
        for emp in self:
            emp.sh_my_team = emp.id in team.ids

    def _search_sh_my_team(self, operator, value):
        return _team_domain(self, operator, value)

    def _sh_my_team_ids(self):
        """Direct reports of the current user, counting every equal head."""
        ids = set()
        for me in self.env.user.employee_ids.sudo():
            ids.update(me._sh_direct_reports().ids)
        return list(ids)

    @api.depends('parent_id', 'department_id', 'department_id.manager_ids')
    def _compute_sh_manager_ids(self):
        for emp in self:
            heads = emp.sudo()._sh_heads()
            emp.sh_manager_ids = heads
            emp.sh_co_manager_ids = heads - emp.parent_id

    def _sh_heads(self):
        """All equal heads of this employee: Odoo keeps one manager (parent_id); its
        co-heads are the other heads of the department where that manager is a head."""
        self.ensure_one()
        boss = self.parent_id
        if not boss:
            return self.browse()
        dept = self.department_id
        while dept:
            if boss in dept.manager_ids:
                return dept.manager_ids - self
            dept = dept.parent_id
        return boss

    def _sh_direct_reports(self):
        """Employees for whom self is one of the (equal) heads."""
        self.ensure_one()
        heads = self.env['hr.department'].search([('manager_ids', 'in', self.id)]).manager_ids | self
        candidates = self.search([('parent_id', 'in', heads.ids), ('id', '!=', self.id)])
        return candidates.filtered(lambda e: self in e._sh_heads())

    def _sh_all_reports(self):
        found, todo = self.browse(), self._sh_direct_reports()
        while todo:
            found |= todo
            nxt = self.browse()
            for emp in todo:
                nxt |= emp._sh_direct_reports()
            todo = nxt - found - self
        return found


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sh_manager_ids = fields.Many2many(
        'hr.employee.public', compute='_compute_sh_manager_ids', string='ხელმძღვანელი')
    sh_co_manager_ids = fields.Many2many(
        'hr.employee.public', compute='_compute_sh_manager_ids', string='სხვა თანაბარი ხელმძღვანელები')

    sh_my_team = fields.Boolean(compute='_compute_sh_my_team', search='_search_sh_my_team', string='ჩემი გუნდი')

    def _compute_sh_my_team(self):
        team = self.env['hr.employee']._sh_my_team_ids()
        for emp in self:
            emp.sh_my_team = emp.id in team

    def _search_sh_my_team(self, operator, value):
        return _team_domain(self.env['hr.employee'], operator, value)

    def _compute_sh_manager_ids(self):
        for emp in self:
            heads = self.env['hr.employee'].sudo().browse(emp.id)._sh_heads()
            emp.sh_manager_ids = self.browse(heads.ids)
            emp.sh_co_manager_ids = self.browse([h.id for h in heads if h.id != emp.parent_id.id])
