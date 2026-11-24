"""Who sees which task (record rules in security/project_rules.xml).

An employee sees only the jobs he takes part in - as assignee, main responsible or reviewer - and
then the whole job: the main task, every step of its sequence and every sub-task, not only his own
part (`sh_party_user_ids`). Being in the department is not enough.

Wider sight is given per person, on the page "დავალებების ხილვა" (Projects - Configuration):
- "ყველა დავალებას ხედავს" - every task of every department;
- "დეპარტამენტები" - every task of these departments (sub-departments included);
- "თანამშრომლები" - the jobs these people take part in;
- "დაქვემდებარებულები" - the same for everyone below him in the employees' hierarchy.
Project administrators see everything, as before.

One job can also be opened to chosen people: "დამატებით ხედავენ" on the task form
(`sh_extra_viewer_ids`, set by the main responsible, a reviewer or an administrator). They see the
whole job the task belongs to (`sh_job_viewer_ids`) - and only see it.

Seeing is not changing: who may change a task is decided as before (the write rule
`rule_sh_task_department_write`, task_edit_lock.py, the flow checks).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

SEE_FIELDS = ('sh_see_all_tasks', 'sh_see_subordinates', 'sh_see_department_ids', 'sh_see_user_ids')
PEOPLE_FIELDS = ('user_ids', 'reviewer_ids', 'sh_responsible_id', 'sh_extra_viewer_ids')
LINK_FIELDS = ('parent_id', 'child_ids', 'depend_on_ids', 'dependent_ids', 'sh_parallel_ids')


class ResUsers(models.Model):
    _inherit = 'res.users'

    sh_see_all_tasks = fields.Boolean(
        'ყველა დავალებას ხედავს', help="ხედავს ყველა დეპარტამენტის ყველა დავალებას (მხოლოდ სანახავად).")
    sh_see_subordinates = fields.Boolean(
        'დაქვემდებარებულები',
        help="ხედავს იმ დავალებებს, რომლებშიც მისი დაქვემდებარებულები მონაწილეობენ "
             "(თანამშრომლების იერარქიის მიხედვით - ბარათზე „ხელმძღვანელი“).")
    sh_see_department_ids = fields.Many2many(
        'hr.department', 'sh_user_see_department_rel', 'user_id', 'department_id', string='დეპარტამენტები',
        help="ხედავს ამ დეპარტამენტების (და მათი ქვედეპარტამენტების) ყველა დავალებას.")
    sh_see_user_ids = fields.Many2many(
        'res.users', 'sh_user_see_user_rel', 'user_id', 'seen_user_id', string='თანამშრომლები',
        domain="[('share', '=', False)]",
        help="ხედავს იმ დავალებებს, რომლებშიც ეს თანამშრომლები მონაწილეობენ.")
    # used by the access rules: himself + the listed people + his subordinates
    sh_see_user_all_ids = fields.Many2many(
        'res.users', 'sh_user_see_user_all_rel', 'user_id', 'seen_user_id', string='ვის დავალებებს ხედავს',
        compute='_compute_sh_see_all_ids', compute_sudo=True)
    # ... and the listed departments with their sub-departments
    sh_see_department_all_ids = fields.Many2many(
        'hr.department', 'sh_user_see_department_all_rel', 'user_id', 'department_id',
        string='დეპარტამენტები (ქვედეპარტამენტებით)', compute='_compute_sh_see_all_ids', compute_sudo=True)

    @api.depends('sh_see_user_ids', 'sh_see_subordinates', 'sh_see_department_ids')
    def _compute_sh_see_all_ids(self):
        Employee = self.env['hr.employee'].sudo()
        Department = self.env['hr.department'].sudo()
        for user in self:
            seen = user | user.sh_see_user_ids
            if user.sh_see_subordinates:
                mine = Employee.search([('user_id', '=', user.id)])
                if mine:
                    seen |= Employee.search([('id', 'child_of', mine.ids)]).user_id
            user.sh_see_user_all_ids = seen
            depts = user.sh_see_department_ids
            user.sh_see_department_all_ids = Department.search([('id', 'child_of', depts.ids)]) if depts else depts

    def write(self, vals):
        if not any(f in vals for f in SEE_FIELDS):
            return super().write(vals)
        user = self.env.user
        # only the system administrator: the page is in his menu only, and nobody else may set it by hand
        if not (self.env.su or user.has_group('base.group_system')):
            raise AccessError(_("დავალებების ხილვას ცვლის მხოლოდ სისტემის ადმინისტრატორი."))
        res = super().write(vals)
        # the access rules are cached per user
        self.env.registry.clear_cache()
        return res


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # "დაქვემდებარებულები" follows the hierarchy: a new manager / account changes who sees what
    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        self.env.registry.clear_cache()
        return employees

    def write(self, vals):
        res = super().write(vals)
        if 'parent_id' in vals or 'user_id' in vals or 'active' in vals:
            self.env.registry.clear_cache()
        return res


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    @api.model_create_multi
    def create(self, vals_list):
        departments = super().create(vals_list)
        self.env.registry.clear_cache()
        return departments

    def write(self, vals):
        res = super().write(vals)
        if 'parent_id' in vals:
            self.env.registry.clear_cache()
        return res


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # everyone who takes part in the job this task belongs to (see _sh_job_tasks) - kept by _sh_sync_party
    sh_party_user_ids = fields.Many2many(
        'res.users', 'sh_task_party_rel', 'task_id', 'user_id', string='დავალების მონაწილეები', copy=False,
        help="მთელი დავალების (მთავარი დავალება, თანმიმდევრობის ნაბიჯები, ქვედავალებები) "
             "შემსრულებლები, პასუხისმგებლები და შემმოწმებლები - ისინი მთელ დავალებას ხედავენ.")

    # "დამატებით ხედავენ": people let in to this one job, whatever their department or list
    sh_extra_viewer_ids = fields.Many2many(
        'res.users', 'sh_task_extra_viewer_rel', 'task_id', 'user_id', string='დამატებით ხედავენ',
        domain="[('share', '=', False)]", copy=True, tracking=True,
        help="ეს ადამიანები ხედავენ ამ დავალებას მთლიანად (მთავარი დავალება, ნაბიჯები, ქვედავალებები), "
             "მხოლოდ სანახავად. ამატებს მთავარი პასუხისმგებელი, შემმოწმებელი ან ადმინისტრატორი.")
    # the extra viewers of the whole job - used by the access rules, kept by _sh_sync_party
    sh_job_viewer_ids = fields.Many2many(
        'res.users', 'sh_task_job_viewer_rel', 'task_id', 'user_id', string='მთელ დავალებას დამატებით ხედავენ',
        copy=False)

    def _sh_job_tasks(self):
        """These tasks with everything tied to them: the sequence (previous, next, parallel tasks)
        and the sub-task tree - as superuser, archived ones too."""
        seen = todo = self.sudo().with_context(active_test=False)
        while todo:
            todo = (todo.depend_on_ids | todo.dependent_ids | todo.sh_parallel_ids
                    | todo.parent_id | todo.child_ids) - seen
            seen |= todo
        return seen

    def _sh_sync_party(self):
        todo = self.sudo().with_context(active_test=False).exists()
        while todo:
            job = todo[0]._sh_job_tasks()
            users = job.user_ids | job.reviewer_ids | job.sh_responsible_id
            viewers = job.sh_extra_viewer_ids
            for task in job:
                if task.sh_party_user_ids != users:
                    task.sh_party_user_ids = [(6, 0, users.ids)]
                if task.sh_job_viewer_ids != viewers:
                    task.sh_job_viewer_ids = [(6, 0, viewers.ids)]
            todo -= job

    @api.model
    def _sh_party_init(self):
        """Once, for the tasks made before this field."""
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('steelhouse_task_flow.party_init'):
            return
        self.sudo().with_context(active_test=False).search([])._sh_sync_party()
        ICP.set_param('steelhouse_task_flow.party_init', '1')

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._sh_sync_party()
        return tasks

    def write(self, vals):
        links = any(f in vals for f in LINK_FIELDS)
        # a cut link splits the job in two: both halves are recounted
        before = self._sh_job_tasks() if links else self.browse()
        res = super().write(vals)
        if links or any(f in vals for f in PEOPLE_FIELDS):
            (before | self.sudo().with_context(active_test=False))._sh_sync_party()
        return res

    def unlink(self):
        rest = self._sh_job_tasks() - self.sudo().with_context(active_test=False)
        res = super().unlink()
        rest._sh_sync_party()
        return res
