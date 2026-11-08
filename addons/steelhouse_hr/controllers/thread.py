from odoo.http import request

from odoo.addons.mail.controllers.thread import ThreadController


class SteelhouseThreadController(ThreadController):
    """A person who was addressed personally in a record's chatter (@mention or as recipient)
    may reply there even without access to the record. The record itself stays closed to them."""

    @classmethod
    def _get_thread_with_access_for_post(cls, thread_model, thread_id, **kwargs):
        thread = super()._get_thread_with_access_for_post(thread_model, thread_id, **kwargs)
        if thread or not thread_model or not thread_id or request.env.user._is_public():
            return thread
        partner = request.env.user.partner_id
        addressed = request.env['mail.message'].sudo().search_count([
            ('model', '=', thread_model), ('res_id', '=', int(thread_id)),
            '|', ('partner_ids', 'in', partner.id), ('notification_ids.res_partner_id', '=', partner.id),
        ], limit=1)
        if addressed and thread_model in request.env:
            return request.env[thread_model].sudo().browse(int(thread_id)).exists()
        return thread
