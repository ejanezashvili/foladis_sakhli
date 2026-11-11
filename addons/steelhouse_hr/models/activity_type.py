from markupsafe import Markup

from odoo import api, fields, models, tools

# Types the system schedules by itself (e.g. time off approval): not offered for manual activities.
# The type already set on an activity stays visible.
TYPE_DOMAIN = ("['&', '|', ('res_model', '=', False), ('res_model', '=', res_model), "
               "'|', ('sh_system_only', '=', False), ('id', '=', activity_type_id)]")


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    sh_system_only = fields.Boolean(
        string='მხოლოდ სისტემური',
        help="ამ ტიპის აქტივობას მხოლოდ სისტემა ქმნის (მაგ. შვებულების დამტკიცება); ხელით არჩევისას არ ჩანს.")


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    activity_type_id = fields.Many2one(domain=TYPE_DOMAIN)


class MailActivitySchedule(models.TransientModel):
    _inherit = 'mail.activity.schedule'

    activity_type_id = fields.Many2one(domain=TYPE_DOMAIN)


class MailActivityDoneNotice(models.Model):
    """When someone marks as done an activity that another person gave them,
    that person gets a notice (Odoo / e-mail, by their notification setting)."""
    _inherit = 'mail.activity'

    @api.model
    def sh_my_open_activities(self, res_model, res_id):
        """Open activities of the current user on a record (for the Inbox "mark as done" button)."""
        acts = self.search([('res_model', '=', res_model), ('res_id', '=', int(res_id)), ('user_id', '=', self.env.uid)])
        return [{'id': a.id, 'name': a.summary or a.activity_type_id.name,
                 'note': tools.html2plaintext(a.note or '').strip()[:120],
                 'deadline': a.date_deadline.strftime('%d/%m/%Y') if a.date_deadline else ''} for a in acts]

    def _action_done(self, feedback=False, attachment_ids=None):
        notices = []
        for act in self:
            creator = act.create_uid
            if (act.res_model and act.res_id and creator and creator.id > 2 and creator.active and not creator.share
                    and creator != self.env.user and not act.activity_type_id.sh_system_only):
                what = act.summary or act.activity_type_id.name or ''
                notices.append((act.res_model, act.res_id, creator.partner_id.id, what, act.note))
        res = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)
        for model, res_id, partner_id, what, note in notices:
            record = self.env[model].sudo().browse(res_id).exists()
            if not record or not hasattr(record, 'message_notify'):
                continue
            body = Markup("<p>✅ <b>%s</b> შეასრულა: %s</p>") % (self.env.user.name, what)
            if note and not tools.is_html_empty(note):
                body += Markup("<div>%s</div>") % note
            if feedback:
                body += Markup("<p>შედეგი: %s</p>") % feedback
            record.message_notify(partner_ids=[partner_id], author_id=self.env.user.partner_id.id,
                                  subject="შესრულდა: %s" % what, body=body)
        return res


SH_LEAVE_STATUS = {'confirm': 'დასამტკიცებელი', 'validate1': 'მეორე დამტკიცება'}


class ResUsersActivityMenu(models.Model):
    """Activities menu (clock icon): under "Time Off" show whose request it is, the dates
    and its status, so it is clear without opening it."""
    _inherit = 'res.users'

    @api.model
    def _get_activity_groups(self):
        groups = super()._get_activity_groups()
        for group in groups:
            if group.get('model') != 'hr.leave':
                continue
            acts = self.env['mail.activity'].search(
                [('user_id', '=', self.env.uid), ('res_model', '=', 'hr.leave')], order='date_deadline, id')
            leaves = self.env['hr.leave'].browse(dict.fromkeys(acts.mapped('res_id'))).exists()._filtered_access('read')
            lines = []
            for leave in leaves.sudo():
                dates = leave.request_date_from.strftime('%d.%m')
                if leave.request_date_to and leave.request_date_to != leave.request_date_from:
                    dates += '–' + leave.request_date_to.strftime('%d.%m')
                status = SH_LEAVE_STATUS.get(leave.state) or dict(
                    leave._fields['state']._description_selection(self.env)).get(leave.state, '')
                lines.append({'id': leave.id, 'employee': leave.employee_id.name,
                              'text': f"{leave.holiday_status_id.name} · {dates}", 'status': status})
            group['sh_lines'] = lines[:5]
            group['sh_more'] = max(0, len(lines) - 5)
        return groups

