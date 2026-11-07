from odoo import api, fields, models


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
    sh_extra_job_ids = fields.Many2many(
        'hr.job', 'hr_employee_sh_extra_job_rel', 'employee_id', 'job_id', string='დამატებითი პოზიციები',
        help="სხვა დეპარტამენტის პოზიციები, რომლებსაც თანამშრომელი ძირითადი პოზიციის გარდა იკავებს.")

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
