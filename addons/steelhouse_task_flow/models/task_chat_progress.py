"""Progress in the shared chat ("საერთო ჩატი"): when a part of a task - a sequence step or a
sub-task - is finished (confirmed, state "done"), OdooBot writes into the chat of the whole task
how many parts are done ("3/5 შესრულებულია"), what is left and who does it. One message per
task and save; nothing for templates, cancelled parts are not counted."""
from markupsafe import Markup

from odoo import _, fields, models

BAR_CELLS = 10


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_progress_owner(self):
        """The task whose chat gets the progress of this part: the main task of the sequence for a
        step, the parent for a sub-task. Empty when the task is not a part of anything."""
        self.ensure_one()
        task = self.sudo()
        if task.dependent_ids:
            main = task._sh_chain_main()
            if main != task:
                return main
        return task.parent_id

    def _sh_progress_parts(self):
        """Steps and sub-tasks of this task, cancelled ones left out, in working order."""
        self.ensure_one()
        task = self.sudo()
        parts = task._sh_all_previous() | task.with_context(active_test=False).child_ids
        return parts.filtered(lambda t: t.state != '1_canceled' and not t.is_template).sorted(
            lambda t: (t.sh_is_step and 0 or 1, t.sequence, t.id))

    def _sh_progress_line(self, part):
        who = ', '.join(part.user_ids.mapped('name')) or _("შემსრულებელი არ არის")
        line = Markup("• <b>%s</b> — %s") % (part.name, who)
        if part.date_deadline:
            day = fields.Datetime.context_timestamp(self.with_context(tz='Asia/Tbilisi'), part.date_deadline)
            line += Markup(" · ⏰ %s") % day.strftime('%d.%m.%Y')
        return line

    def _sh_progress_body(self, just_done):
        self.ensure_one()
        parts = self._sh_progress_parts()
        total = len(parts)
        left = parts.filtered(lambda t: t.state != '1_done')
        done = total - len(left)
        if not total:
            return False
        cells = round(BAR_CELLS * done / total)
        bar = '🟩' * cells + '⬜' * (BAR_CELLS - cells)
        closed = Markup(', ').join(Markup("„%s“") % t.name for t in just_done)
        lines = [Markup("✅ %s %s") % (_("დასრულდა:"), closed)]
        if left:
            lines.insert(0, Markup("📊 <b>%s</b>") % _("%(done)s/%(total)s შესრულებულია", done=done, total=total))
            lines.insert(1, Markup("%s %s%%") % (bar, round(100 * done / total)))
            lines.append(Markup("⏳ <b>%s</b>") % _("დარჩენილია %s:", len(left)))
            lines += [self._sh_progress_line(part) for part in left]
            lines.append(Markup("🙏 %s") % _("გთხოვთ, დარჩენილი დავალებები დროულად შეასრულოთ."))
        else:
            lines.insert(0, Markup("🎉 <b>%s</b>") % _(
                "%(done)s/%(total)s — ყველა დავალება შესრულებულია!", done=done, total=total))
            lines.insert(1, Markup("%s 100%%") % bar)
            lines.append(Markup("👏 %s") % _("გმადლობთ! მთავარი დავალება მზად არის საბოლოო შემოწმებისთვის."))
        return Markup("<br/>").join(lines)

    def _sh_post_progress(self, just_done):
        """OdooBot's message in the shared chat of this task."""
        self.ensure_one()
        task = self.sudo()
        if task.is_template or not task.project_id or task.state == '1_canceled':
            return
        body = task._sh_progress_body(just_done)
        if not body:
            return
        task._sh_ensure_chat()
        channel = task.sh_channel_id
        if channel:
            channel.message_post(body=body, author_id=self.env.ref('base.partner_root').id,
                                 message_type='comment', subtype_xmlid='mail.mt_comment')

    def write(self, vals):
        open_before = self.browse()
        if 'state' in vals or 'stage_id' in vals:
            open_before = self.sudo().filtered(lambda t: t.state != '1_done' and not t.is_template)
        res = super().write(vals)
        by_owner = {}
        for part in open_before.filtered(lambda t: t.state == '1_done'):
            owner = part._sh_progress_owner()
            if owner:
                by_owner.setdefault(owner, self.browse())
                by_owner[owner] |= part
        for owner, parts in by_owner.items():
            owner._sh_post_progress(parts)
        return res
