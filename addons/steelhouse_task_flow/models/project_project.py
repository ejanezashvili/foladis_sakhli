from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    sh_is_department = fields.Boolean(
        string='დეპარტამენტი', default=False, index=True,
        help="დეპარტამენტის პროექტი (ჩანს „დეპარტამენტებში“). "
             "მოხსნილი — კონკრეტული პროექტი (ჩანს „პროექტებში“).")
