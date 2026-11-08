from odoo import api, fields, models

CHANNELS = [
    ('email', 'ელფოსტით'),
    ('inbox', 'Odoo-ში'),
    ('both', 'ორივე: Odoo-ში და ელფოსტით'),
]


class ResUsers(models.Model):
    """Third notification choice "both": stored as Odoo's "In Odoo" (inbox) plus a flag,
    so everything that checks for inbox users keeps working."""
    _inherit = 'res.users'

    sh_notify_email_too = fields.Boolean(string='შეტყობინება ელფოსტითაც')
    sh_notification_channel = fields.Selection(
        CHANNELS, string='შეტყობინებები', compute='_compute_sh_notification_channel',
        inverse='_inverse_sh_notification_channel',
        help="სად მოგივიდეთ შეტყობინებები (@მონიშვნა, მიმოწერა, აქტივობის დანიშვნა):\n"
             "- ელფოსტით\n- Odoo-ში (💬)\n- ორივე ადგილას")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['sh_notify_email_too', 'sh_notification_channel']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['sh_notify_email_too', 'sh_notification_channel']

    @api.depends('notification_type', 'sh_notify_email_too')
    def _compute_sh_notification_channel(self):
        for user in self:
            if user.notification_type == 'inbox':
                user.sh_notification_channel = 'both' if user.sh_notify_email_too else 'inbox'
            else:
                user.sh_notification_channel = 'email'

    def _inverse_sh_notification_channel(self):
        # read all choices first: each write recomputes the field for the other records
        choices = {user: user.sh_notification_channel or 'email' for user in self}
        for user, channel in choices.items():
            user.write({
                'notification_type': 'email' if channel == 'email' else 'inbox',
                'sh_notify_email_too': channel == 'both',
            })


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread_by_email(self, message, recipients_data, *args, **kwargs):
        # "both" users are inbox users (they already got the Odoo notification):
        # send them the e-mail too
        uids = [r['uid'] for r in recipients_data if r.get('notif') == 'inbox' and r.get('uid')]
        both = set(self.env['res.users'].sudo().search(
            [('id', 'in', uids), ('sh_notify_email_too', '=', True)]).ids) if uids else set()
        if both:
            recipients_data = [dict(r, notif='email') if r.get('notif') == 'inbox' and r.get('uid') in both else r
                               for r in recipients_data]
            self = self.with_context(sh_skip_existing_notification=True)
        return super(MailThread, self)._notify_thread_by_email(message, recipients_data, *args, **kwargs)


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    @api.model_create_multi
    def create(self, vals_list):
        # one notification per message and person: for "both" users the inbox one already exists
        if self.env.context.get('sh_skip_existing_notification'):
            keys = [(v.get('mail_message_id'), v.get('res_partner_id')) for v in vals_list if v.get('res_partner_id')]
            if keys:
                existing = self.sudo().search([
                    ('mail_message_id', 'in', list({k[0] for k in keys})),
                    ('res_partner_id', 'in', list({k[1] for k in keys}))])
                taken = {(n.mail_message_id.id, n.res_partner_id.id) for n in existing}
                vals_list = [v for v in vals_list
                             if (v.get('mail_message_id'), v.get('res_partner_id')) not in taken]
        return super().create(vals_list)
