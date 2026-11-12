from odoo import Command, api, fields, models

PEOPLE_FIELDS = ('user_ids', 'reviewer_ids', 'sh_responsible_id')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # "საერთო ჩატი": one Discuss group chat per task with everyone on it
    sh_channel_id = fields.Many2one('discuss.channel', string='საერთო ჩატი', copy=False, readonly=True)

    def _sh_chat_name(self):
        self.ensure_one()
        return '%s%s' % (self.sh_number and self.sh_number + ' ' or '', self.name or '')

    def _sh_chat_partners(self):
        self.ensure_one()
        users = self.user_ids | self.reviewer_ids | self.sh_responsible_id | self.create_uid
        return users.filtered(lambda u: u.active and not u.share).partner_id

    def _sh_ensure_chat(self):
        """Create the group chat if missing; add anyone on the task who is not in it yet."""
        Channel = self.env['discuss.channel'].sudo()
        for task in self.filtered(lambda t: not t.is_template and t.project_id):
            partners = task._sh_chat_partners()
            channel = task.sudo().sh_channel_id
            if not channel:
                channel = Channel.create({
                    'name': task._sh_chat_name(),
                    'channel_type': 'group',
                    'channel_member_ids': [Command.create({'partner_id': p.id}) for p in partners],
                })
                task.sudo().with_context(sh_flow_internal=True).sh_channel_id = channel
                continue
            missing = partners - channel.channel_member_ids.partner_id
            if missing:
                channel.write({'channel_member_ids': [Command.create({'partner_id': p.id}) for p in missing]})

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        # sub-tasks get their chat on first open, so a chain does not create a pile of chats
        tasks.filtered(lambda t: not t.parent_id)._sh_ensure_chat()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in PEOPLE_FIELDS):
            self.filtered('sh_channel_id')._sh_ensure_chat()
        if 'name' in vals:
            for task in self.filtered('sh_channel_id'):
                task.sh_channel_id.sudo().name = task._sh_chat_name()
        return res

    def action_sh_open_chat(self):
        """Button "საერთო ჩატი": opens the task's group chat in Discuss."""
        self.ensure_one()
        self._sh_ensure_chat()
        channel = self.sudo().sh_channel_id
        me = self.env.user.partner_id
        if me not in channel.channel_member_ids.partner_id:  # can see the task -> may join its chat
            channel.write({'channel_member_ids': [Command.create({'partner_id': me.id})]})
        active_id = 'discuss.channel_%d' % channel.id
        return {
            'type': 'ir.actions.client',
            'tag': 'mail.action_discuss',
            'context': {'active_id': active_id},
            'params': {'active_id': active_id},
        }
