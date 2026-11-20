"""Role "კონფიდენციალური": its members see every confidential task without being listed on it.

The role is the group `group_sh_confidential` (record rule `rule_sh_task_confidential`). It is managed
from the Employees app, menu "კონფიდენციალური": employee cards, "x" removes, the "+" card adds in
one click (static/src/conf_role). Only project administrators manage it."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP = 'steelhouse_task_flow.group_sh_confidential'


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    sh_conf_member = fields.Boolean('კონფიდენციალური', compute='_compute_sh_conf_member',
                                    search='_search_sh_conf_member')

    def _compute_sh_conf_member(self):
        users = self.env.ref(GROUP).sudo().user_ids
        for emp in self:
            emp.sh_conf_member = bool(emp.user_id) and emp.user_id in users

    def _search_sh_conf_member(self, operator, value):
        users = self.env.ref(GROUP).sudo().user_ids
        if operator in ('in', 'not in'):
            positive = (True in value) == (operator == 'in')
        else:
            positive = bool(value) == (operator in ('=', '=='))
        return [('user_id', 'in' if positive else 'not in', users.ids)]

    @api.model
    def _sh_conf_check(self):
        user = self.env.user
        if not (self.env.su or user.has_group('project.group_project_manager')
                or user.has_group('base.group_system')):
            raise UserError(_("კონფიდენციალურის სიას ცვლის მხოლოდ ადმინისტრატორი."))

    @api.model
    def sh_conf_candidates(self, term=''):
        """Employees with a user account that are not in the role yet (for the "+" dialog)."""
        self._sh_conf_check()
        domain = [('user_id', '!=', False), ('sh_conf_member', '=', False)]
        if term:
            domain += ['|', '|', ('name', 'ilike', term), ('job_title', 'ilike', term),
                       ('department_id.name', 'ilike', term)]
        emps = self.sudo().search(domain, order='name', limit=40)
        return [{'id': e.id, 'name': e.name, 'job': e.job_title or '',
                 'department': e.department_id.name or ''} for e in emps]

    def sh_conf_add(self):
        self._sh_conf_check()
        users = self.sudo().user_id
        if not users:
            raise UserError(_("ამ თანამშრომელს სისტემის ანგარიში არ აქვს."))
        self.env.ref(GROUP).sudo().write({'user_ids': [(4, u.id) for u in users]})
        return True

    def action_sh_conf_remove(self):
        self._sh_conf_check()
        users = self.sudo().user_id
        if users:
            self.env.ref(GROUP).sudo().write({'user_ids': [(3, u.id) for u in users]})
        return True

    @api.model
    def _sh_conf_init_members(self):
        """Once: the first members agreed with the client (2026-11-21)."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('steelhouse_task_flow.conf_role_init'):
            return
        names = ['დავითი სალთხუციშვილი', 'ზეზვა სალთხუციშვილი', 'სოფიკო ერაძე', 'გიორგი მდივნიშვილი']
        users = self.env['hr.employee'].sudo().search([('name', 'in', names)]).user_id
        users |= self.env['res.users'].sudo().search([('name', '=', 'Elene J.')], limit=1)
        self.env.ref(GROUP).sudo().write({'user_ids': [(4, u.id) for u in users]})
        ICP.set_param('steelhouse_task_flow.conf_role_init', '1')
