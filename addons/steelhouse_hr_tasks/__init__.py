from . import models
from . import wizard


def _sh_hr_tasks_post_init(env):
    """The board „კადრები“ takes the columns of the department boards (the shared flow) and its own code."""
    project = env.ref('steelhouse_hr_tasks.project_sh_hr', raise_if_not_found=False)
    if not project:
        return
    other = env['project.project'].search(
        [('sh_is_department', '=', True), ('is_template', '=', False), ('id', '!=', project.id), ('type_ids', '!=', False)],
        limit=1)
    if other and not project.type_ids:
        project.type_ids = [(6, 0, other.type_ids.ids)]
        project.privacy_visibility = other.privacy_visibility
    if 'sh_code' in project._fields and not project.sh_code:
        project.sh_code = 'HR'
    env['steelhouse.hr.task.config']._sh_get()
