from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_template_count = fields.Integer(compute='_compute_sh_template_count', string='შაბლონები')

    def _compute_sh_template_count(self):
        count = self.env['project.task'].search_count([('is_template', '=', True)])
        for task in self:
            task.sh_template_count = count

    def action_sh_save_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('შაბლონად შენახვა'),
            'res_model': 'steelhouse.task.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id, 'default_name': self.name},
        }

    def action_sh_open_templates(self):
        return self.env['ir.actions.act_window']._for_xml_id('steelhouse_task_flow.action_sh_task_templates')

    def action_sh_use_template(self):
        """New task from this template, in the department's first stage; opens it."""
        self.ensure_one()
        if not self.is_template:
            raise UserError(_("ეს დავალება შაბლონი არ არის."))
        first = self.project_id.type_ids.filtered(lambda s: s.sh_kind == 'new')[:1] or self.project_id.type_ids[:1]
        values = {'name': self.name}
        if first:
            values['stage_id'] = first.id
        task_id = self.action_create_from_template(values)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }


class TaskTemplateWizard(models.TransientModel):
    _name = 'steelhouse.task.template.wizard'
    _description = 'დავალების შაბლონად შენახვა'

    task_id = fields.Many2one('project.task', required=True, ondelete='cascade')
    name = fields.Char('შაბლონის სახელი', required=True)

    def action_confirm(self):
        self.ensure_one()
        task = self.task_id
        if not task.project_id:
            raise UserError(_("შაბლონად შენახვისთვის დავალებას დეპარტამენტი უნდა ჰქონდეს."))
        template = task.with_context(sh_flow_internal=True).copy({
            'name': self.name.strip(),
            'is_template': True,
            'sh_repeat': False,
            'date_deadline': False,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("შაბლონი „%s“ შენახულია.", template.name),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
