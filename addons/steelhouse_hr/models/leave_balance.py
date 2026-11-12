from odoo import fields, models, tools


class SteelhouseLeaveBalance(models.Model):
    """Days balance of the current year: one line per employee and time off type
    (every active type, also the ones not used yet)."""
    _name = 'steelhouse.leave.balance'
    _description = 'შვებულების ბალანსი'
    _auto = False
    _order = 'sequence, leave_type_id'

    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', readonly=True)
    user_id = fields.Many2one('res.users', string='მომხმარებელი', readonly=True)
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი', readonly=True)
    leave_type_id = fields.Many2one('hr.leave.type', string='შვებულების ტიპი', readonly=True)
    sequence = fields.Integer(readonly=True)
    requires_allocation = fields.Boolean(string='საჭიროებს ნაშთს', readonly=True)
    allocated = fields.Float(string='გამოყოფილი', readonly=True, digits=(16, 1))
    used = fields.Float(string='გამოყენებული', readonly=True, digits=(16, 1))
    pending = fields.Float(string='დასამტკიცებელი', readonly=True, digits=(16, 1))
    remaining = fields.Float(string='დარჩენილი', readonly=True, digits=(16, 1),
                             help="გამოყოფილს გამოკლებული გამოყენებული (ტიპებზე, რომლებიც ნაშთს საჭიროებს).")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT
                    e.id * 10000 + t.id AS id,
                    e.id AS employee_id,
                    e.user_id AS user_id,
                    v.department_id AS department_id,
                    t.id AS leave_type_id,
                    t.sequence AS sequence,
                    t.requires_allocation AS requires_allocation,
                    COALESCE(al.days, 0) AS allocated,
                    COALESCE(lv.used, 0) AS used,
                    COALESCE(lv.pending, 0) AS pending,
                    CASE WHEN t.requires_allocation
                         THEN COALESCE(al.days, 0) - COALESCE(lv.used, 0) END AS remaining
                FROM hr_employee e
                LEFT JOIN hr_version v ON v.id = e.current_version_id
                JOIN res_company c ON c.id = e.company_id
                JOIN res_partner cp ON cp.id = c.partner_id
                CROSS JOIN hr_leave_type t
                LEFT JOIN (
                    SELECT employee_id, holiday_status_id, SUM(number_of_days) AS days
                      FROM hr_leave_allocation
                     WHERE state = 'validate'
                       AND date_from < date_trunc('year', now()) + interval '1 year'
                       AND (date_to IS NULL OR date_to >= date_trunc('year', now()))
                  GROUP BY employee_id, holiday_status_id
                ) al ON al.employee_id = e.id AND al.holiday_status_id = t.id
                LEFT JOIN (
                    SELECT employee_id, holiday_status_id,
                           SUM(CASE WHEN state = 'validate' THEN number_of_days ELSE 0 END) AS used,
                           SUM(CASE WHEN state IN ('confirm', 'validate1') THEN number_of_days ELSE 0 END) AS pending
                      FROM hr_leave
                     WHERE date_trunc('year', request_date_from) = date_trunc('year', now())
                  GROUP BY employee_id, holiday_status_id
                ) lv ON lv.employee_id = e.id AND lv.holiday_status_id = t.id
                WHERE e.active AND t.active
                  AND (t.company_id IS NULL OR t.company_id = e.company_id)
                  -- types of other countries' localizations are hidden in Odoo too
                  AND (t.country_id IS NULL OR t.country_id = cp.country_id)
            )
        """)
