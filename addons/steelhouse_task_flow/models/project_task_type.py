from odoo import fields, models

STAGE_KINDS = [
    ('new', 'ახალი'),
    ('accepted', 'მიღებული'),
    ('in_progress', 'მიმდინარე'),
    ('on_hold', 'შეჩერებული'),
    ('review', 'შემოწმებაზე'),
    ('returned', 'დაბრუნებული'),
    ('done', 'დასრულებული'),
    ('cancelled', 'გაუქმებული'),
]


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    sh_kind = fields.Selection(
        STAGE_KINDS, string='სტადიის ტიპი',
        help="რას ნიშნავს ეს სტადია პროცესში. მისით სისტემა წყვეტს სტატუსს, "
             "მიზეზის მოთხოვნას და ვის შეუძლია გადაყვანა.")
