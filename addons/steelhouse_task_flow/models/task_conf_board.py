"""Confidential tasks live only on the "კონფიდენციალური" board (Projects app, top menu).

- every other board / list / grouping / search of tasks leaves them out (web_search_read,
  web_read_group), as do the department card counts, "მთავარი" and the company week;
- the board (context `sh_conf_board`) shows them in the four columns, departments on the left,
  the numbers on top (`sh_conf_summary`);
- the menu is shown only to the role "კონფიდენციალური" and to people on at least one confidential
  task (group `group_sh_conf_viewer`, kept in sync by `_sh_conf_sync_viewers`).
"""
from odoo import api, fields, models
from odoo.fields import Domain

CLOSED = ('1_done', '1_canceled')
VIEWER = 'steelhouse_task_flow.group_sh_conf_viewer'
ROLE = 'steelhouse_task_flow.group_sh_confidential'
PEOPLE_FIELDS = ('sh_confidential', 'user_ids', 'reviewer_ids', 'sh_responsible_id', 'sh_confidential_viewer_ids',
                 'active', 'is_template')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # ------------------------------------------------------------------ off every other board
    def _sh_hide_confidential(self, domain):
        if self.env.context.get('sh_conf_board'):
            return Domain.AND([Domain(domain or []), Domain('sh_confidential', '=', True)])
        text = str(domain or '')
        # specific tasks (forms, lists of ids) or an explicit filter on the flag stay as asked
        if "'sh_confidential'" in text or "'id'" in text:
            return domain
        return Domain.AND([Domain(domain or []), Domain('sh_confidential', '=', False)])

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(self._sh_hide_confidential(domain), specification, offset=offset,
                                       limit=limit, order=order, count_limit=count_limit)

    @api.model
    def web_read_group(self, domain, groupby, aggregates=(), limit=None, offset=0, order=None, **kwargs):
        return super().web_read_group(self._sh_hide_confidential(domain), groupby, aggregates=aggregates,
                                      limit=limit, offset=offset, order=order, **kwargs)

    # ------------------------------------------------------------------ the board's numbers
    @api.model
    def sh_conf_summary(self, domain=None):
        # the same tasks the board shows (sequence steps hidden as everywhere, see task_card_lists)
        domain = self._sh_hide_steps(list(domain or []) + [('sh_confidential', '=', True), ('is_template', '=', False)])
        tasks = self.with_context(sh_conf_board=True).search(domain)
        count = lambda phase: len(tasks.filtered(lambda t: t.sh_phase == phase))
        return {
            'total': len(tasks),
            'new': count('new'),
            'wip': count('wip'),
            'review': count('review'),
            'overdue': len(tasks.filtered('sh_is_overdue')),
        }

    # ------------------------------------------------------------------ who sees the menu
    @api.model
    def _sh_conf_sync_viewers(self):
        """The viewer group = the role + everyone on a confidential task."""
        tasks = self.sudo().with_context(active_test=False).search(
            [('sh_confidential', '=', True), ('is_template', '=', False)])
        users = (tasks.user_ids | tasks.reviewer_ids | tasks.sh_responsible_id | tasks.sh_confidential_viewer_ids
                 | tasks.create_uid | self.env.ref(ROLE).sudo().user_ids)
        users = users.filtered(lambda u: not u.share)
        group = self.env.ref(VIEWER).sudo()
        if set(group.user_ids.ids) != set(users.ids):
            group.write({'user_ids': [(6, 0, users.ids)]})

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        if any(tasks.mapped('sh_confidential')):
            self._sh_conf_sync_viewers()
        return tasks

    def write(self, vals):
        touch = any(f in vals for f in PEOPLE_FIELDS) and (
            vals.get('sh_confidential') or any(self.sudo().mapped('sh_confidential')))
        res = super().write(vals)
        if touch:
            self._sh_conf_sync_viewers()
        return res

    def unlink(self):
        conf = any(self.sudo().mapped('sh_confidential'))
        res = super().unlink()
        if conf:
            self.env['project.task']._sh_conf_sync_viewers()
        return res


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _sh_count(self, field, domain):
        # department / project card numbers never count confidential tasks
        return super()._sh_count(field, list(domain) + [('sh_confidential', '=', False)])


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        res = super().write(vals)
        # the role changed: its members see the menu too
        if 'user_ids' in vals and self.env.ref(ROLE, raise_if_not_found=False) in self:
            self.env['project.task']._sh_conf_sync_viewers()
        return res
