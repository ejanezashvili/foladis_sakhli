from odoo import api, fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    # used by the access rules: who heads this department or any department above it
    sh_all_manager_user_ids = fields.Many2many(
        'res.users', 'sh_department_all_manager_rel', 'department_id', 'user_id',
        string='ხელმძღვანელები (ზემდგომების ჩათვლით)',
        compute='_compute_sh_all_manager_user_ids', store=True, recursive=True)

    @api.depends('manager_ids.user_id', 'manager_id.user_id', 'parent_id.sh_all_manager_user_ids')
    def _compute_sh_all_manager_user_ids(self):
        for dep in self:
            dep.sh_all_manager_user_ids = (dep.manager_ids.user_id | dep.manager_id.user_id
                                           | dep.parent_id.sh_all_manager_user_ids)
