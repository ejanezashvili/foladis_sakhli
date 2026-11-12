from markupsafe import Markup, escape

from odoo import api, fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    deputy_id = fields.Many2one(
        'hr.employee', string='შემცვლელი', tracking=True, index=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="ხელმძღვანელის შემცვლელი მისი არყოფნისას.")
    manager_ids = fields.Many2many(
        'hr.employee', 'hr_department_co_manager_rel', 'department_id', 'employee_id',
        string='ხელმძღვანელები',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="დეპარტამენტის ხელმძღვანელები. რამდენიმე ხელმძღვანელს თანაბარი უფლებები აქვს.")

    sh_head_title = fields.Char(
        string='ხელმძღვანელის პოზიცია',
        help="სტრუქტურის მიხედვით ხელმძღვანელის პოზიცია; იერარქიაში ჩანს, როცა ხელმძღვანელი ვაკანტურია.")
    sh_heads_html = fields.Html(
        compute='_compute_sh_heads_html', sanitize=False,
        help="All equal heads with photo and name, for the department cards (display only).")
    sh_headcount = fields.Integer(
        compute='_compute_sh_headcount', string='ქვეშ მყოფი თანამშრომლები',
        help="ყველა, ვინც ამ ერთეულის ხელმძღვანელების ქვეშაა (ქვედანაყოფების ჩათვლით, ხელმძღვანელების გარეშე).")

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        # a new unit without a name yet: no "Parent / False" in the title
        super()._compute_complete_name()
        for department in self:
            if not department.name:
                department.complete_name = False

    @api.depends('manager_ids', 'manager_ids.name')
    def _compute_sh_heads_html(self):
        for dept in self:
            dept.sh_heads_html = Markup('').join(
                Markup('<span class="o_sh_head_pill"><img src="/web/image/hr.employee.public/%s/avatar_128" alt=""/>%s</span>')
                % (head.id, escape(head.name or ''))
                for head in dept.manager_ids
            ) or False

    def _sh_team(self):
        """Everyone in this unit and its sub-units, except this unit's heads."""
        self.ensure_one()
        return self.env['hr.employee'].sudo().search(
            [('department_id', 'child_of', self.id), ('id', 'not in', self.manager_ids.ids)])

    def _compute_sh_headcount(self):
        for dept in self:
            dept.sh_headcount = len(dept._sh_team()) if dept.id else 0

    def sh_action_team(self):
        self.ensure_one()
        res_model = 'hr.employee' if self.env['hr.employee'].has_access('read') else 'hr.employee.public'
        return {
            'name': self.name,
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'views': [(False, 'list'), (False, 'kanban'), (False, 'form')],
            'domain': [('id', 'in', self._sh_team().ids)],
            'context': {'create': False},
        }

    @api.model
    def sh_positions_data(self):
        """Positions of every department with the people holding them (heads excluded,
        they are on the card). Used by the department hierarchy view."""
        jobs = self.env['hr.job'].sudo().search([('department_id', '!=', False)], order='sequence, id')
        employees = self.env['hr.employee'].sudo().search([('department_id', '!=', False)])
        result = {}
        for dept in self.sudo().search([]):
            members = employees.filtered(lambda e: e.department_id == dept) - dept.manager_ids
            positions = []
            for job in jobs.filtered(lambda j: j.department_id == dept):
                holders = members.filtered(lambda e: e.job_id == job) | employees.filtered(
                    lambda e: job in e.sh_extra_job_ids)
                positions.append({'id': job.id, 'name': job.name,
                                  'employees': [{'id': e.id, 'name': e.name} for e in holders]})
            others = members.filtered(lambda e: e.job_id.department_id != dept)
            if others:
                positions.append({'id': 0, 'name': 'პოზიციის გარეშე',
                                  'employees': [{'id': e.id, 'name': e.name} for e in others]})
            if positions:
                result[str(dept.id)] = positions  # string keys: JSON and XML-RPC
        return result

    def _sh_top_department(self, company_id=False):
        """The company's top unit ("ფოლადის სახლი"): the oldest department without a parent."""
        company_id = company_id or self.env.company.id
        return self.sudo().search([('parent_id', '=', False), ('company_id', 'in', [company_id, False])],
                                  order='id', limit=1)

    # A new department goes under the company's top unit unless another parent is chosen,
    # so it does not appear as a second top level next to the company.
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'parent_id' in fields and not res.get('parent_id'):
            res['parent_id'] = self._sh_top_department(res.get('company_id')).id or False
        return res

    # Odoo needs a single manager_id (employee managers, approvals). It is kept in sync
    # with manager_ids and hidden in the views, so all heads look the same.
    @api.model_create_multi
    def create(self, vals_list):
        top = self._sh_top_department()
        if top:
            for vals in vals_list:
                if not vals.get('parent_id') and 'parent_id' not in vals:
                    vals['parent_id'] = self._sh_top_department(vals.get('company_id')).id
        departments = super().create(vals_list)
        for dept, vals in zip(departments, vals_list):
            dept._sh_sync_heads(list_changed=bool(vals.get('manager_ids')))
        return departments

    def write(self, vals):
        res = super().write(vals)
        if 'manager_ids' in vals or 'manager_id' in vals:
            self._sh_sync_heads(list_changed='manager_ids' in vals)
        if {'manager_ids', 'manager_id', 'parent_id'} & set(vals):
            # heads or place in the structure changed: direct managers below follow
            self.env['hr.employee'].sudo().search(
                [('department_id', 'child_of', self.ids)])._sh_set_structure_manager()
        return res

    def _sh_sync_heads(self, list_changed):
        for dept in self:
            if dept.manager_id and dept.manager_id not in dept.manager_ids and not list_changed:
                super(HrDepartment, dept).write({'manager_ids': [(4, dept.manager_id.id)]})
            elif dept.manager_id not in dept.manager_ids or (not dept.manager_id and dept.manager_ids):
                super(HrDepartment, dept).write({'manager_id': dept.manager_ids[:1].id})


class HrJob(models.Model):
    _inherit = 'hr.job'

    # Many positions share a name ("ასისტენტი" in 7 units): when choosing one, show its unit.
    @api.depends_context('sh_job_department')
    @api.depends('department_id')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('sh_job_department'):
            for job in self.filtered('department_id'):
                unit = job.department_id.sudo().complete_name.split(' / ', 1)[-1]
                job.display_name = f'{job.name} ({unit})'

