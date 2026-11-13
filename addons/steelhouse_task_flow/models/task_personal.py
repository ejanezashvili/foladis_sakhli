from datetime import timedelta

from odoo import api, fields, models

# "ჩემი დავალებები" columns (personal stages), by creation date
INBOX, TODAY, WEEK, MONTH = 'შემოსულები', 'დღეს', 'ეს კვირა', 'ეს თვე'


class ProjectTask(models.Model):
    _inherit = 'project.task'

    def _sh_personal_bucket(self, today):
        created = self.create_date and fields.Datetime.context_timestamp(self, self.create_date).date()
        if not created:
            return INBOX
        if created == today:
            return TODAY
        if created >= today - timedelta(days=today.weekday()):
            return WEEK
        if created >= today.replace(day=1):
            return MONTH
        return INBOX

    def _sh_place_personal(self):
        """Put each open task into its assignees' personal column by creation date."""
        Stage = self.env['project.task.type'].sudo()
        Personal = self.env['project.task.stage.personal'].sudo()
        today = fields.Date.context_today(self)
        cache = {}
        for task in self.filtered(lambda t: not t.is_template and t.state not in ('1_done', '1_canceled')):
            bucket = task._sh_personal_bucket(today)
            for user in task.user_ids:
                if user.id not in cache:
                    stages = Stage.search([('user_id', '=', user.id)])
                    cache[user.id] = {s.name: s for s in stages}
                stage = cache[user.id].get(bucket)
                if not stage:
                    continue
                link = Personal.search([('task_id', '=', task.id), ('user_id', '=', user.id)], limit=1)
                if link and link.stage_id != stage:
                    link.stage_id = stage
                elif not link:
                    Personal.create({'task_id': task.id, 'user_id': user.id, 'stage_id': stage.id})

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks._sh_place_personal()
        return tasks

    def write(self, vals):
        res = super().write(vals)
        if 'user_ids' in vals:
            self._sh_place_personal()
        return res

    @api.model
    def _cron_sh_place_personal(self):
        self.search([('is_template', '=', False), ('state', 'not in', ['1_done', '1_canceled']),
                     ('user_ids', '!=', False)])._sh_place_personal()
