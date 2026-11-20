from odoo import api, fields, models, _
from odoo.exceptions import UserError

DEPT_DOMAIN = "[('sh_is_department', '=', True), ('is_template', '=', False)]"


def _ids_from_commands(commands):
    """Ids a many2many value of create() ends up with: [(6, 0, ids)], [(4, id)], [id, ...]."""
    ids = []
    for cmd in commands or []:
        if isinstance(cmd, int):
            ids.append(cmd)
        elif cmd[0] == 6:
            ids = list(cmd[2])
        elif cmd[0] == 4:
            ids.append(cmd[1])
    return ids


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # "დეპარტამენტი" on the form: several departments can be chosen. project_id stays the main one
    # (flow, numbers, reports) and is always one of them - see _sh_sync_departments.
    sh_department_project_ids = fields.Many2many(
        'project.project', 'sh_task_department_project_rel', 'task_id', 'project_id',
        string='დეპარტამენტები', domain=DEPT_DOMAIN, tracking=True,
        help="რამდენიმე დეპარტამენტის არჩევისას დავალებას ხედავს ამ დეპარტამენტების ყველა თანამშრომელი "
             "(მხოლოდ სანახავად). პირველი არჩეული - ძირითადი დეპარტამენტია. "
             "კონფიდენციალურ დავალებაზე არ მოქმედებს.")
    # used by the access rules (security/project_rules.xml): HR departments whose every employee
    # sees the task - filled only when several departments are chosen (one department: as before)
    sh_view_department_ids = fields.Many2many(
        'hr.department', 'sh_task_view_department_rel', 'task_id', 'department_id',
        string='ხედავენ დეპარტამენტები', compute='_compute_sh_view_department_ids', store=True)
    # the task is "mine": I am an assignee or the main responsible - shown in bold on cards and lists
    sh_is_mine = fields.Boolean(compute='_compute_sh_is_mine')

    def init(self):
        super().init()
        # tasks made before this field: their department is the one they already have
        self.env.cr.execute("""
            INSERT INTO sh_task_department_project_rel (task_id, project_id)
            SELECT t.id, t.project_id
              FROM project_task t
              JOIN project_project p ON p.id = t.project_id AND p.sh_is_department
             WHERE NOT EXISTS (SELECT 1 FROM sh_task_department_project_rel r WHERE r.task_id = t.id)
        """)

    @api.depends('sh_department_project_ids', 'sh_department_project_ids.sh_department_id')
    def _compute_sh_view_department_ids(self):
        for task in self:
            depts = task.sudo().sh_department_project_ids
            task.sh_view_department_ids = depts.sh_department_id if len(depts) > 1 else False

    @api.depends('user_ids', 'sh_responsible_id')
    @api.depends_context('uid')
    def _compute_sh_is_mine(self):
        user = self.env.user
        for task in self:
            task.sh_is_mine = user in task.user_ids or task.sh_responsible_id == user

    # ------------------------------------------------------------------ main department <-> departments
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'sh_department_project_ids' in fields_list and res.get('project_id') \
                and not res.get('sh_department_project_ids'):
            project = self.env['project.project'].sudo().browse(res['project_id'])
            if project.sh_is_department:
                res['sh_department_project_ids'] = [(6, 0, project.ids)]
        return res

    @api.onchange('sh_department_project_ids')
    def _onchange_sh_department_project_ids(self):
        ids = self.sh_department_project_ids._origin.ids
        if self.project_id._origin.id not in ids:
            self.project_id = self.env['project.project'].browse(ids[:1])

    def _sh_sync_departments(self, project_changed=False):
        """The main department (project_id) is always one of the chosen departments."""
        for task in self.sudo().with_context(sh_dept_sync=True):
            depts, main = task.sh_department_project_ids, task.project_id
            if main in depts or not (depts or main.sh_is_department):
                continue
            if main.sh_is_department and (project_changed or not depts):
                task.sh_department_project_ids = [(4, main.id)]
            elif depts:
                task.project_id = depts[0]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            ids = _ids_from_commands(vals.get('sh_department_project_ids'))
            if ids and not vals.get('project_id'):
                vals['project_id'] = ids[0]
        tasks = super().create(vals_list)
        tasks._sh_sync_departments(project_changed=True)
        return tasks

    def write(self, vals):
        if ('stage_id' in vals or 'state' in vals) and not self.env.context.get('sh_flow_internal'):
            self._sh_check_viewer_move()
        res = super().write(vals)
        if ('project_id' in vals or 'sh_department_project_ids' in vals) \
                and not self.env.context.get('sh_dept_sync'):
            self._sh_sync_departments(project_changed='project_id' in vals
                                      and 'sh_department_project_ids' not in vals)
        return res

    # ------------------------------------------------------------------ view only
    def _sh_sees_by_department_only(self):
        """The user reaches the task only as an employee of one of its departments."""
        self.ensure_one()
        user = self.env.user
        task = self.sudo()
        return not (
            user in task.user_ids or user in task.reviewer_ids or user == task.sh_responsible_id
            or user == task.create_uid or user in task.sh_confidential_viewer_ids
            or user in task.project_id.sh_department_id.sh_all_manager_user_ids
        ) and user in task.sh_view_department_ids.member_ids.user_id

    def _sh_check_viewer_move(self):
        if self.env.su or self._sh_is_edit_admin():
            return
        for task in self:
            if task._sh_sees_by_department_only():
                raise UserError(_(
                    "„%s“ თქვენთვის მხოლოდ სანახავადაა (დეპარტამენტის მიხედვით) - სტადიას ვერ შეცვლით.",
                    task.name))
