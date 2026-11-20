"""Task boards show four columns instead of the stages: ახალი / მუშავდება / შემოწმებაზე / დასრულებული.

The stages (and their kinds) stay as they are - reminders, work time, approvals, reports keep using
them. `sh_phase` only groups them for the board: "მუშავდება" = მიღებული, მიმდინარე, შეჩერებული,
დაბრუნებული. Dragging a card to another column moves the task to the matching stage, with the
usual rules. A main task of a sequence leaves "ახალი" by itself when its first step is started.
"""
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError

PHASES = [
    ('new', 'ახალი'),
    ('wip', 'მუშავდება'),
    ('review', 'შემოწმებაზე'),
    ('done', 'დასრულებული'),
    ('cancelled', 'გაუქმებული'),
]
KIND_PHASE = {
    'new': 'new', 'accepted': 'wip', 'in_progress': 'wip', 'on_hold': 'wip', 'returned': 'wip',
    'review': 'review', 'done': 'done', 'cancelled': 'cancelled',
}
# the stage kind a card gets when it is dropped into a column
PHASE_KIND = {'new': 'new', 'wip': 'in_progress', 'review': 'review', 'done': 'done', 'cancelled': 'cancelled'}
# a step in one of these kinds means the work on the sequence has begun
STARTED_KINDS = ('accepted', 'in_progress', 'review', 'done')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_phase = fields.Selection(
        PHASES, string='ეტაპი', compute='_compute_sh_phase', inverse='_inverse_sh_phase',
        store=True, index=True, group_expand='_read_group_sh_phase',
        help="დაფის სვეტი. „მუშავდება“ აერთიანებს სტადიებს: მიღებული, მიმდინარე, შეჩერებული, დაბრუნებული.")

    @api.depends('stage_id.sh_kind')
    def _compute_sh_phase(self):
        for task in self:
            task.sh_phase = KIND_PHASE.get(task.stage_id.sh_kind, 'wip') if task.stage_id else False

    def _inverse_sh_phase(self):
        """A card dropped into another column: move the task to the matching stage."""
        for task in self:
            kind = task.stage_id.sh_kind
            phase = task.sh_phase
            if not phase or not task.project_id or KIND_PHASE.get(kind, 'wip') == phase:
                continue
            stage = task._sh_stage_of_kind(PHASE_KIND[phase])
            if not stage:
                raise UserError(_("ამ დეპარტამენტს არ აქვს შესაბამისი სტადია."))
            if phase == 'wip' and kind == 'new':
                # starting the work is accepting the task: only its assignee (or an admin)
                task._sh_check_assignee()
            task.write({'stage_id': stage.id})

    @api.model
    def _read_group_sh_phase(self, values, domain):
        """Board columns: the four phases always; "გაუქმებული" only when there are such tasks."""
        return ['new', 'wip', 'review', 'done'] + (['cancelled'] if 'cancelled' in values else [])

    @api.model_create_multi
    def create(self, vals_list):
        # "+" in a column: a new task always starts in its first stage
        for vals in vals_list:
            vals.pop('sh_phase', None)
        ctx = {k: v for k, v in self.env.context.items() if k != 'default_sh_phase'}
        return super(ProjectTask, self.with_context(ctx)).create(vals_list)

    # ------------------------------------------------------------------ the main task follows its steps
    def _sh_start_mains(self):
        """Main tasks still in "ახალი" whose step has been started go to "მიმდინარე"."""
        for main in self.sudo():
            stage = main._sh_stage_of_kind('in_progress')
            if stage and main.stage_id.sh_kind == 'new' and main.state not in ('1_done', '1_canceled'):
                main.with_context(sh_flow_internal=True).write({'stage_id': stage.id})

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals and not self.env.context.get('sh_flow_internal'):
            mains = self.browse()
            for step in self.sudo().filtered(lambda t: t.sh_is_step and t.stage_id.sh_kind in STARTED_KINDS):
                main = step._sh_chain_main()
                if main != step and main._sh_is_main() and main.stage_id.sh_kind == 'new':
                    mains |= main
            mains._sh_start_mains()
        return res

    def _sh_notify_steps_done(self):
        """Every step is confirmed by its reviewer: the main task goes to "შემოწმებაზე" by itself and
        waits for one more confirmation - of its own reviewers (it shows up in "დადასტურებები")."""
        self.ensure_one()
        main = self.sudo()
        stage = main._sh_stage_of_kind('review')
        steps = main._sh_all_previous()
        if (stage and main.stage_id.sh_kind in ('new', 'accepted', 'in_progress', 'returned')
                and main.state not in ('1_done', '1_canceled') and any(s.state == '1_done' for s in steps)):
            try:
                with self.env.cr.savepoint():
                    main.write({'stage_id': stage.id})
            except UserError:
                # something still blocks the review (e.g. required evidence): only tell the people
                return super()._sh_notify_steps_done()
            partners = main.reviewer_ids.filtered(lambda u: u.active and not u.share).partner_id
            main.with_context(mail_post_autofollow=False).message_post(
                body=Markup("✅ <b>%s</b>") % _("ყველა ნაბიჯი დადასტურდა - დავალება გადავიდა შემოწმებაზე, საჭიროა საბოლოო დადასტურება."),
                partner_ids=partners.ids, message_type='comment' if partners else 'notification',
                subtype_xmlid='mail.mt_comment' if partners else 'mail.mt_note')
            return None
        return super()._sh_notify_steps_done()

    @api.model
    def _sh_sync_main_phase(self):
        """Run on every module update: main tasks left in "ახალი" although a step is already started."""
        mains = self.sudo().search([
            ('is_template', '=', False), ('sh_is_step', '=', False), ('depend_on_ids', '!=', False),
            ('stage_id.sh_kind', '=', 'new'), ('state', 'not in', ['1_done', '1_canceled'])])
        mains.filtered(lambda m: any(s.stage_id.sh_kind in STARTED_KINDS for s in m._sh_all_previous()))._sh_start_mains()
