from odoo import fields, models, tools


class SteelhouseLeaveBalance(models.Model):
    """Days balance by period, kept for ever (2026-11-20):

    - a type with dated allocations (paid time off - the quarters): one line per period
      (allocation): granted, used and pending inside the period, remaining; when the period
      is over its unused days are "burned" (not carried over);
    - a type with open allocations (compensatory days): one line per employee and type -
      everything granted minus everything used;
    - a type without allocations (unpaid, sick list, trip ...): one line per employee, type and
      year with the days used (the current year also for types not used yet).
    """
    _name = 'steelhouse.leave.balance'
    _description = 'შვებულების ბალანსი'
    _auto = False
    _order = 'period_from desc, sequence, leave_type_id'

    employee_id = fields.Many2one('hr.employee', string='თანამშრომელი', readonly=True)
    user_id = fields.Many2one('res.users', string='მომხმარებელი', readonly=True)
    department_id = fields.Many2one('hr.department', string='დეპარტამენტი', readonly=True)
    leave_type_id = fields.Many2one('hr.leave.type', string='შვებულების ტიპი', readonly=True)
    sequence = fields.Integer(readonly=True)
    requires_allocation = fields.Boolean(string='საჭიროებს ნაშთს', readonly=True)
    period_from = fields.Date(string='პერიოდი: დან', readonly=True)
    period_to = fields.Date(string='პერიოდი: მდე', readonly=True)
    status = fields.Selection([('current', 'მიმდინარე'), ('ended', 'დასრულდა'), ('future', 'მომავალი')],
                              string='სტატუსი', readonly=True)
    allocated = fields.Float(string='მიენიჭა', readonly=True, digits=(16, 1))
    used = fields.Float(string='გამოიყენა', readonly=True, digits=(16, 1))
    pending = fields.Float(string='დასამტკიცებელი', readonly=True, digits=(16, 1))
    remaining = fields.Float(string='დარჩა', readonly=True, digits=(16, 1),
                             help="მინიჭებულს გამოკლებული გამოყენებული; დასრულებულ პერიოდში - ეს დღეები დაიწვა.")
    burned = fields.Float(string='დაიწვა', readonly=True, digits=(16, 1),
                          help="დასრულებული პერიოდის გამოუყენებელი დღეები (შემდეგ პერიოდზე არ გადადის).")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
            WITH types AS (
                SELECT t.id, t.sequence, t.requires_allocation, t.company_id, t.country_id
                  FROM hr_leave_type t
                 WHERE t.active
            ), emps AS (
                SELECT e.id, e.user_id, v.department_id, e.company_id, cp.country_id
                  FROM hr_employee e
                  LEFT JOIN hr_version v ON v.id = e.current_version_id
                  JOIN res_company c ON c.id = e.company_id
                  JOIN res_partner cp ON cp.id = c.partner_id
                 WHERE e.active
            ), pairs AS (
                -- types of other countries' localizations are hidden in Odoo too
                SELECT e.id AS employee_id, e.user_id, e.department_id, t.id AS type_id, t.sequence, t.requires_allocation
                  FROM emps e CROSS JOIN types t
                 WHERE (t.company_id IS NULL OR t.company_id = e.company_id)
                   AND (t.country_id IS NULL OR t.country_id = e.country_id)
            ), lv AS (
                SELECT employee_id, holiday_status_id, request_date_from AS day, state, number_of_days
                  FROM hr_leave
                 WHERE state IN ('validate', 'confirm', 'validate1')
            )
            -- 1) dated allocations: one line per period
            SELECT a.id::bigint * 10 + 1 AS id,
                   p.employee_id, p.user_id, p.department_id, p.type_id AS leave_type_id, p.sequence,
                   TRUE AS requires_allocation,
                   a.date_from AS period_from, a.date_to AS period_to,
                   CASE WHEN a.date_to < CURRENT_DATE THEN 'ended'
                        WHEN a.date_from > CURRENT_DATE THEN 'future' ELSE 'current' END AS status,
                   a.number_of_days AS allocated,
                   COALESCE(u.used, 0) AS used,
                   COALESCE(u.pending, 0) AS pending,
                   a.number_of_days - COALESCE(u.used, 0) AS remaining,
                   CASE WHEN a.date_to < CURRENT_DATE THEN GREATEST(a.number_of_days - COALESCE(u.used, 0), 0)
                        ELSE 0 END AS burned
              FROM hr_leave_allocation a
              JOIN pairs p ON p.employee_id = a.employee_id AND p.type_id = a.holiday_status_id
              LEFT JOIN LATERAL (
                    SELECT SUM(CASE WHEN l.state = 'validate' THEN l.number_of_days ELSE 0 END) AS used,
                           SUM(CASE WHEN l.state <> 'validate' THEN l.number_of_days ELSE 0 END) AS pending
                      FROM lv l
                     WHERE l.employee_id = a.employee_id AND l.holiday_status_id = a.holiday_status_id
                       AND l.day BETWEEN a.date_from AND a.date_to
              ) u ON TRUE
             WHERE a.state = 'validate' AND a.date_to IS NOT NULL

            UNION ALL
            -- 2) open allocations (compensatory days): all granted minus all used
            SELECT (p.employee_id::bigint * 100000 + p.type_id) * 10 + 2 AS id,
                   p.employee_id, p.user_id, p.department_id, p.type_id, p.sequence,
                   TRUE, o.first_day, NULL::date, 'current',
                   o.days,
                   COALESCE(u.used, 0), COALESCE(u.pending, 0),
                   o.days - COALESCE(u.used, 0), 0
              FROM (SELECT employee_id, holiday_status_id, MIN(date_from) AS first_day, SUM(number_of_days) AS days
                      FROM hr_leave_allocation
                     WHERE state = 'validate' AND date_to IS NULL
                  GROUP BY employee_id, holiday_status_id) o
              JOIN pairs p ON p.employee_id = o.employee_id AND p.type_id = o.holiday_status_id
              LEFT JOIN LATERAL (
                    SELECT SUM(CASE WHEN l.state = 'validate' THEN l.number_of_days ELSE 0 END) AS used,
                           SUM(CASE WHEN l.state <> 'validate' THEN l.number_of_days ELSE 0 END) AS pending
                      FROM lv l
                     WHERE l.employee_id = o.employee_id AND l.holiday_status_id = o.holiday_status_id
              ) u ON TRUE

            UNION ALL
            -- 3) types without allocations: days used per year (this year for every type, zero too)
            SELECT ((p.employee_id::bigint * 100000 + p.type_id) * 10000 + y.year) * 10 + 3 AS id,
                   p.employee_id, p.user_id, p.department_id, p.type_id, p.sequence,
                   FALSE, make_date(y.year, 1, 1), make_date(y.year, 12, 31),
                   CASE WHEN y.year < EXTRACT(YEAR FROM CURRENT_DATE) THEN 'ended'
                        WHEN y.year > EXTRACT(YEAR FROM CURRENT_DATE) THEN 'future' ELSE 'current' END,
                   0,
                   COALESCE(SUM(CASE WHEN l.state = 'validate' THEN l.number_of_days END), 0),
                   COALESCE(SUM(CASE WHEN l.state <> 'validate' THEN l.number_of_days END), 0),
                   0, 0
              FROM pairs p
              JOIN (SELECT DISTINCT employee_id, holiday_status_id, EXTRACT(YEAR FROM day)::int AS year FROM lv
                    UNION
                    SELECT employee_id, type_id, EXTRACT(YEAR FROM CURRENT_DATE)::int FROM pairs) y
                ON y.employee_id = p.employee_id AND y.holiday_status_id = p.type_id
              LEFT JOIN lv l ON l.employee_id = p.employee_id AND l.holiday_status_id = p.type_id
                            AND EXTRACT(YEAR FROM l.day)::int = y.year
             WHERE NOT p.requires_allocation
          GROUP BY p.employee_id, p.user_id, p.department_id, p.type_id, p.sequence, y.year
            )
        """)
