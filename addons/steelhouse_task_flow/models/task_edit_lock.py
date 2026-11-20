"""Who may edit a task: only its main responsible, its reviewers and administrators.

Everyone else (assignees included) can still work on the task - move it between stages, use the
buttons (accept, performed, hold ...), sub-tasks, the sequence, chat and attachments - but cannot
change its data (name, description, deadline, assignees ...). In the description they may only
tick / untick the checklist items; the text itself stays as it is.

The check sits on `web_save` - the call behind every save from a form, list or kanban card - so
the module's own buttons and widgets (they call their own methods) are not affected."""
import re

import lxml.html

from odoo import _, models
from odoo.exceptions import UserError

# what anyone who sees the task may still change from the screen (the flow has its own rules)
FREE_FIELDS = frozenset({'stage_id', 'state', 'personal_stage_type_id', 'personal_stage_type_ids'})


def _desc_signature(html):
    """The description without what a tick changes: tags, links / images and text
    (classes and other attributes - "o_checked", editor marks - are left out)."""
    html = str(html or '').strip()
    if not html:
        return []
    root = lxml.html.fragment_fromstring(html, create_parent='div')

    def clean(text):
        return re.sub(r'\s+', ' ', (text or '').replace(chr(160), ' ')).strip()

    sig = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        item = (el.tag, el.get('href'), el.get('src'), clean(el.text), clean(el.tail))
        # an empty line (<p><br></p>) is not content
        if item not in (('p', None, None, '', ''), ('br', None, None, '', '')):
            sig.append(item)
    return sig[1:]


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_is_edit_admin(self):
        user = self.env.user
        return (self.env.su or user.has_group('project.group_project_manager')
                or user.has_group('base.group_system'))

    def _sh_can_edit(self):
        self.ensure_one()
        user = self.env.user
        return self._sh_is_edit_admin() or user == self.sh_responsible_id or user in self.reviewer_ids

    def _sh_check_can_edit(self, vals):
        if all(f in FREE_FIELDS for f in vals) or self._sh_is_edit_admin():
            return
        for task in self:
            if task._sh_can_edit():
                continue
            locked = [f for f in vals if f not in FREE_FIELDS
                      and not (f == 'description' and task._sh_only_ticks(vals[f]))]
            if not locked:
                continue
            labels = [task._fields[f].get_description(self.env)['string'] for f in locked if f in task._fields]
            message = _(
                "დავალებაში ცვლილების შეტანა შეუძლია მხოლოდ მთავარ პასუხისმგებელს, შემმოწმებელს "
                "ან ადმინისტრატორს.\nდავალება: %(task)s\nშეცვლილი ველები: %(fields)s",
                task=task.name, fields=', '.join(labels) or '-')
            if 'description' in locked:
                message += _("\nაღწერაში შეგიძლიათ მხოლოდ საკონტროლო სიის პუნქტების მონიშვნა.")
            raise UserError(message)

    def _sh_only_ticks(self, new_description):
        """True when the new description differs from the saved one only by checklist ticks."""
        self.ensure_one()
        return _desc_signature(self.description) == _desc_signature(new_description)

    def web_save(self, vals, *args, **kwargs):
        if self:  # an existing task (a new one is being created - anyone may create)
            self._sh_check_can_edit(vals)
        return super().web_save(vals, *args, **kwargs)

    def web_save_multi(self, vals_list, *args, **kwargs):
        # several list rows edited at once
        for task, vals in zip(self, vals_list):
            task._sh_check_can_edit(vals)
        return super().web_save_multi(vals_list, *args, **kwargs)
