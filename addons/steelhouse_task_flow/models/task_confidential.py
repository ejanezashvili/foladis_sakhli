"""8.3 confidential tasks: seen only by project administrators, the main responsible, assignees,
reviewers, the creator and the extra viewers (record rule `rule_sh_task_confidential`).
Only administrators and the main responsible may switch it on/off or change the extra viewers.
Sub-tasks follow their parent."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

CONF_FIELDS = ('sh_confidential', 'sh_confidential_viewer_ids')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_confidential = fields.Boolean('კონფიდენციალური', copy=True, tracking=True, index=True)
    sh_confidential_viewer_ids = fields.Many2many(
        'res.users', 'sh_task_confidential_viewer_rel', 'task_id', 'user_id', string='დამატებით ხედავენ',
        domain="[('share', '=', False)]", copy=True)
    sh_can_confidential = fields.Boolean(compute='_compute_sh_can_confidential')

    def _sh_is_conf_admin(self):
        return self.env.su or self.env.user.has_group('project.group_project_manager')

    @api.depends_context('uid')
    @api.depends('sh_responsible_id')
    def _compute_sh_can_confidential(self):
        admin = self._sh_is_conf_admin()
        for task in self:
            task.sh_can_confidential = admin or task.sh_responsible_id == self.env.user

    def _sh_conf_allowed_users(self):
        self.ensure_one()
        return (self.sh_responsible_id | self.user_ids | self.reviewer_ids | self.create_uid
                | self.sh_confidential_viewer_ids)

    def _sh_check_conf_rights(self, vals):
        if not any(f in vals for f in CONF_FIELDS) or self._sh_is_conf_admin() \
                or self.env.context.get('sh_conf_internal'):
            return
        for task in self:
            if task.sh_responsible_id != self.env.user:
                raise UserError(_("„კონფიდენციალურის“ მონიშვნა და „დამატებით ხედავენ“ შეუძლია მხოლოდ "
                                  "ადმინისტრატორს ან მთავარ პასუხისმგებელს."))

    def _sh_conf_cleanup(self):
        """Confidential: drop followers who may not see it; add the extra viewers to the chat."""
        for task in self.sudo().filtered('sh_confidential'):
            allowed = task._sh_conf_allowed_users()
            for follower in task.message_follower_ids:
                users = follower.partner_id.user_ids
                if users and not (users & allowed) and not any(
                        u.has_group('steelhouse_task_flow.group_sh_confidential') for u in users):
                    follower.unlink()
            if task.sh_channel_id:
                missing = task.sh_confidential_viewer_ids.partner_id - task.sh_channel_id.channel_member_ids.partner_id
                if missing:
                    task.sh_channel_id.add_members(partner_ids=missing.ids)

    def _sh_conf_to_children(self):
        for task in self:
            kids = task.sudo().with_context(active_test=False).child_ids
            if kids:
                kids.with_context(sh_conf_internal=True).write({
                    'sh_confidential': task.sh_confidential,
                    'sh_confidential_viewer_ids': [(6, 0, task.sh_confidential_viewer_ids.ids)]})

    @api.model_create_multi
    def create(self, vals_list):
        Task = self.env['project.task']
        for vals in vals_list:
            if (vals.get('sh_confidential') or vals.get('sh_confidential_viewer_ids')) and not vals.get('parent_id')                     and not self._sh_is_conf_admin() and not self.env.context.get('sh_conf_internal')                     and vals.get('sh_responsible_id') != self.env.uid:
                raise UserError(_("„კონფიდენციალურის“ მონიშვნა შეუძლია მხოლოდ ადმინისტრატორს ან მთავარ პასუხისმგებელს."))
            parent = vals.get('parent_id') and Task.sudo().browse(vals['parent_id'])
            if parent and parent.sh_confidential:
                vals.setdefault('sh_confidential', True)
                vals.setdefault('sh_confidential_viewer_ids', [(6, 0, parent.sh_confidential_viewer_ids.ids)])
        tasks = super().create(vals_list)
        tasks._sh_conf_cleanup()
        return tasks

    def write(self, vals):
        self._sh_check_conf_rights(vals)
        res = super().write(vals)
        if any(f in vals for f in CONF_FIELDS):
            self._sh_conf_cleanup()
            self._sh_conf_to_children()
        return res

    def _sh_chat_partners(self):
        partners = super()._sh_chat_partners()
        if self.sh_confidential:
            partners |= self.sh_confidential_viewer_ids.filtered(lambda u: u.active and not u.share).partner_id
        return partners
