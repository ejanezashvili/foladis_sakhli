from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # "საბოლოო პროექტი": what was delivered, filled when the task is completed (optional)
    sh_final_note = fields.Text('საბოლოო აღწერა', tracking=True, copy=False)
    sh_final_attachment_ids = fields.Many2many(
        'ir.attachment', 'sh_task_final_attachment_rel', 'task_id', 'attachment_id',
        string='ფოტოები / ფაილები', copy=False)
    sh_done_user_id = fields.Many2one('res.users', 'დაასრულა', readonly=True, copy=False)
    sh_done_date = fields.Datetime('დასრულების დრო', readonly=True, copy=False)

    sh_is_admin = fields.Boolean(compute='_compute_sh_is_admin')

    def _compute_sh_is_admin(self):
        user = self.env.user
        value = user.has_group('project.group_project_manager') or user.has_group('base.group_system')
        for task in self:
            task.sh_is_admin = value

    def action_sh_review_ok(self):
        """Reviewer confirms (after "დარწმუნებული ხარ?"): final project dialog -> done."""
        self.ensure_one()
        self._sh_check_reviewer('done')
        return self.action_sh_open_final()

    def action_sh_open_final(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('საბოლოო პროექტი — %s', self.name),
            'res_model': 'steelhouse.task.final.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id, 'default_note': self.sh_final_note},
        }


class TaskFinalWizard(models.TransientModel):
    _name = 'steelhouse.task.final.wizard'
    _description = 'საბოლოო პროექტი (დავალების დასრულება)'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade')
    note = fields.Text('აღწერა')
    attachment_ids = fields.Many2many('ir.attachment', string='ფოტოები / ფაილები')

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        if self.attachment_ids:
            self.attachment_ids.sudo().write({'res_model': 'project.task', 'res_id': task.id})
        stage = task._sh_stage_of_kind('done')
        vals = {
            'sh_final_note': self.note,
            'sh_final_attachment_ids': [(4, a.id) for a in self.attachment_ids],
            'sh_done_user_id': self.env.user.id,
            'sh_done_date': fields.Datetime.now(),
        }
        if stage:
            vals['stage_id'] = stage.id
        task.with_context(sh_final_given=True).write(vals)
        return {'type': 'ir.actions.act_window_close'}
