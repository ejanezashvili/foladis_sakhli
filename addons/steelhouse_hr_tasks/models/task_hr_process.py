"""HR processes as tasks (client's documents 2026-11-25, D-10): ვაკანსია / ახალი თანამშრომლის აყვანა / გათავისუფლება.

- The process has its own status (`sh_hr_state`) - the task itself stays in the shared columns of the board
  „კადრები“ (new -> in progress -> done / cancelled), so reports and the home page count it as any task.
- ახალი -> დირექტორთან: the HR manager, only when every required field of the kind is filled;
- დირექტორთან -> დამტკიცებულია / უარყოფილია: only the director (settings); refusing needs a reason;
- on approval: the sub-tasks set in the settings are made for the people chosen there;
- vacancy: დამტკიცებულია -> გადახდაში -> დასრულებულია; the task can be finished only after the approval.
"""
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .hr_constants import ALL_CANDIDATES, KINDS
STATES = [('new', 'ახალი'), ('director', 'დირექტორთან'), ('approved', 'დამტკიცებულია'),
          ('payment', 'გადახდაში'), ('done', 'დასრულებულია'), ('refused', 'უარყოფილია')]
APPROVED = ('approved', 'payment', 'done')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sh_hr_kind = fields.Selection(KINDS, string='კადრების პროცესი', index=True, copy=False)
    sh_hr_state = fields.Selection(STATES, string='პროცესის სტატუსი', default='new', copy=False, tracking=True,
                                   group_expand='_sh_hr_expand_states')
    sh_hr_refuse_reason = fields.Text('უარყოფის მიზეზი', copy=False, tracking=True)
    sh_hr_author_id = fields.Many2one('res.users', string='მომთხოვნი', copy=False, readonly=True)
    sh_hr_is_director = fields.Boolean(compute='_compute_sh_hr_roles')
    sh_hr_is_manager = fields.Boolean(compute='_compute_sh_hr_roles')
    sh_hr_missing = fields.Char(compute='_compute_sh_hr_missing', string='შესავსებია')
    # the form of task_flow hides the sub-tasks tab (the client uses „თანმიმდევრობა“): the HR block lists them itself
    sh_hr_subtask_ids = fields.Many2many('project.task', compute='_compute_sh_hr_subtask_ids', string='ქვედავალებები')
    # required fields of this kind from the settings, as ",name1,name2," (the form marks them required)
    sh_hr_required_fnames = fields.Char(compute='_compute_sh_hr_required_fnames')
    sh_hr_skip_rule_ids = fields.Many2many(
        'steelhouse.hr.subtask.rule', 'sh_task_hr_skip_rule_rel', 'task_id', 'rule_id', string='არ არის საჭირო',
        copy=False, help="ამ მოთხოვნაზე ეს ქვედავალებები არ შეიქმნება (პარამეტრებში „შეიძლება გამოტოვება“).")

    # vacancy / hiring
    sh_hr_position = fields.Char('თანამდებობა / პოზიცია', tracking=True)
    sh_hr_duties = fields.Text('ძირითადი მოვალეობები')
    sh_hr_requirements = fields.Text('ძირითადი მოთხოვნები')
    sh_hr_workplace = fields.Char('სამუშაო ადგილი', tracking=True)
    sh_hr_schedule = fields.Char('სამუშაო გრაფიკი', tracking=True)
    sh_hr_salary = fields.Char('ხელფასი', tracking=True)
    # hiring
    sh_hr_id_number = fields.Char('პირადობის მოწმობის ნომერი', tracking=True)
    sh_hr_phone = fields.Char('ტელეფონის ნომერი', tracking=True)
    sh_hr_address = fields.Char('მისამართი', tracking=True)
    sh_hr_bank_account = fields.Char('ანგარიშის ნომერი', tracking=True)
    sh_hr_email = fields.Char('ელ. ფოსტა', tracking=True)
    sh_hr_start_date = fields.Date('მუშაობის დაწყების თარიღი', tracking=True)
    sh_hr_legal_entity_id = fields.Many2one('steelhouse.legal.entity', string='იურიდიული პირი', tracking=True)
    sh_hr_org_code = fields.Char(related='sh_hr_legal_entity_id.code', string='ორგანიზაციის კოდი')
    # dismissal
    sh_hr_application = fields.Binary('განცხადების ასლი (სკანი)', attachment=True)
    sh_hr_application_name = fields.Char('ფაილის სახელი')
    sh_hr_reason = fields.Text('გათავისუფლების რეალური მიზეზი')
    sh_hr_special = fields.Text('განსაკუთრებული პირობები', help="ჯანმრთელობის პრობლემა და ა.შ. თუ არ არის - „არა“.")
    sh_hr_last_day = fields.Date('ბოლო სამუშაო დღე', tracking=True)
    sh_hr_property = fields.Text('გადაცემული მატერიალური ფასეულობა',
                                 help="ლეპტოპი, ტელეფონი, სხვა აღჭურვილობა. თუ არაფერი - „არა“.")
    sh_hr_need_lawyer = fields.Boolean('იურისტი: დოკუმენტები', default=True)
    sh_hr_need_accountant = fields.Boolean('ბუღალტერი: RS.ge', default=True)
    sh_hr_need_security = fields.Boolean('შიდა უსაფრთხოება', default=True)

    @api.model
    def _sh_hr_expand_states(self, states, domain):
        return [key for key, _label in STATES]

    @api.depends_context('uid')
    def _compute_sh_hr_roles(self):
        config = self.env['steelhouse.hr.task.config']._sh_get()
        user = self.env.user
        for task in self:
            task.sh_hr_is_director = user == config.director_id
            task.sh_hr_is_manager = user in config.hr_manager_ids or user.has_group('base.group_system')

    @api.depends('child_ids')
    def _compute_sh_hr_subtask_ids(self):
        for task in self:
            task.sh_hr_subtask_ids = task.child_ids if task.sh_hr_kind else False

    @api.depends('sh_hr_kind')
    def _compute_sh_hr_required_fnames(self):
        config = self.env['steelhouse.hr.task.config']._sh_get()
        for task in self:
            names = config._sh_required(task.sh_hr_kind) if task.sh_hr_kind else []
            task.sh_hr_required_fnames = ',%s,' % ','.join(names)

    @api.depends(lambda self: ['sh_hr_kind'] + ALL_CANDIDATES)
    def _compute_sh_hr_missing(self):
        for task in self:
            task.sh_hr_missing = ', '.join(task._sh_hr_missing_labels())

    @api.constrains(lambda self: ['sh_hr_kind', 'sh_hr_state'] + ALL_CANDIDATES)
    def _check_sh_hr_required(self):
        """The client's documents: a request without its required fields is not taken for processing - it is
        not saved at all (so HR never gets an incomplete one)."""
        for task in self.filtered(lambda t: t.sh_hr_kind and not t.parent_id and t.sh_hr_state in ('new', 'director')):
            missing = task._sh_hr_missing_labels()
            if missing:
                raise ValidationError(_("მოთხოვნა არ შეინახა - შეავსეთ სავალდებულო ველები: %s", ', '.join(missing)))

    def _sh_hr_missing_labels(self):
        self.ensure_one()
        config = self.env['steelhouse.hr.task.config']._sh_get()
        return [self._fields[f].string for f in config._sh_required(self.sh_hr_kind) if f in self._fields and not self[f]]

    # ------------------------------------------------------------------ create: HR manager, director
    @api.model_create_multi
    def create(self, vals_list):
        """An HR request is created on the board „კადრები“ by the system: its author (a department head) does not
        see that board by the visibility rules (D-4) - he is kept as „მომთხოვნი“ and sees his own request."""
        is_hr = [bool(v.get('sh_hr_kind')) and not v.get('parent_id') for v in vals_list]
        if not any(is_hr):
            return super().create(vals_list)
        config = self.env['steelhouse.hr.task.config']._sh_get()
        project = self.env.ref('steelhouse_hr_tasks.project_sh_hr', raise_if_not_found=False)
        author = self.env.user
        for vals, hr in zip(vals_list, is_hr):
            if not hr:
                continue
            if project:
                vals['project_id'] = project.id
            vals.setdefault('sh_hr_author_id', author.id)
            viewers = [(4, vals['sh_hr_author_id'])]
            # the form fills in the author's department and the author as assignee by default: an HR request
            # belongs to HR only (no department - its people must not see the personal data)
            if project and 'sh_department_project_ids' in self._fields:
                vals['sh_department_project_ids'] = [(6, 0, project.ids)]
            vals.pop('sh_project_id', None)
            if config.hr_manager_ids:
                vals['user_ids'] = [(6, 0, config.hr_manager_ids.ids)]
                vals['reviewer_ids'] = [(6, 0, config.hr_manager_ids.ids)]
            if config.director_id:
                viewers.append((4, config.director_id.id))
            vals['sh_extra_viewer_ids'] = viewers
        others = super().create([v for v, hr in zip(vals_list, is_hr) if not hr])
        hr_tasks = super(ProjectTask, self.sudo()).create([v for v, hr in zip(vals_list, is_hr) if hr]).with_env(self.env)
        for task in hr_tasks:
            task.sudo().message_post(body=_("მოთხოვნა შექმნა: %s", task.sh_hr_author_id.name))
        it_o, it_h = iter(others), iter(hr_tasks)
        return self.browse([next(it_h).id if hr else next(it_o).id for hr in is_hr])

    # ------------------------------------------------------------------ the shared columns follow the process
    def write(self, vals):
        if 'stage_id' in vals and not self.env.context.get('sh_hr_move'):
            kind = self.env['project.task.type'].browse(vals['stage_id']).sh_kind
            for task in self.filtered(lambda t: t.sh_hr_kind and not t.parent_id):
                if task.sh_hr_state in ('new', 'director') and kind not in ('new', 'cancelled'):
                    raise UserError(_("„%s“ დირექტორის დამტკიცებამდე „ახალში“ რჩება - გამოიყენეთ ღილაკები "
                                      "„დირექტორს გაგზავნა“ / „დამტკიცება“.", task.name))
                if task.sh_hr_state == 'refused' and kind not in ('cancelled',):
                    raise UserError(_("„%s“ უარყოფილია დირექტორის მიერ.", task.name))
        res = super().write(vals)
        if 'stage_id' in vals:
            for task in self.filtered(lambda t: t.sh_hr_kind and not t.parent_id):
                if task.stage_id.sh_kind == 'done' and task.sh_hr_state in APPROVED and task.sh_hr_state != 'done':
                    super(ProjectTask, task).write({'sh_hr_state': 'done'})
        return res

    def _sh_hr_move(self, kind):
        stage = self._sh_stage_of_kind(kind)
        if stage and self.stage_id != stage:
            self.sudo().with_context(sh_hr_move=True, sh_reason_given=True).write({'stage_id': stage.id})

    # ------------------------------------------------------------------ buttons
    def action_sh_hr_send(self):
        """HR manager: everything is filled -> to the director."""
        config = self.env['steelhouse.hr.task.config']._sh_get()
        for task in self:
            if not task.sh_hr_is_manager:
                raise UserError(_("დირექტორს აგზავნის HR მენეჯერი (%s).",
                                  ', '.join(config.hr_manager_ids.mapped('name')) or '-'))
            missing = task._sh_hr_missing_labels()
            if missing:
                raise UserError(_("შეავსეთ სავალდებულო ველები: %s", ', '.join(missing)))
            if not config.director_id:
                raise UserError(_("„კადრები → პარამეტრებში“ დირექტორი არ არის მითითებული."))
            task.sudo().write({'sh_hr_state': 'director', 'sh_hr_refuse_reason': False,
                               'sh_extra_viewer_ids': [(4, config.director_id.id)]})
            task.sudo().activity_schedule(
                'mail.mail_activity_data_todo', user_id=config.director_id.id,
                summary=_("დასამტკიცებელია: %s", dict(KINDS)[task.sh_hr_kind]),
                note=_("HR-მა შეამოწმა - დაამტკიცეთ ან უარყავით."))
            task.message_post(body=_("HR-მა შეამოწმა და დირექტორს გაუგზავნა (%s).", config.director_id.name))
        return True

    def _sh_hr_check_director(self):
        config = self.env['steelhouse.hr.task.config']._sh_get()
        for task in self:
            if not task.sh_hr_is_director:
                raise UserError(_("ამტკიცებს / უარყოფს მხოლოდ დირექტორი (%s).", config.director_id.name or '-'))
            if task.sh_hr_state != 'director':
                raise UserError(_("„%s“ დირექტორთან არ არის.", task.name))

    def _sh_hr_close_activities(self, feedback):
        self.sudo().activity_ids.filtered(
            lambda a: a.user_id == self.env.user and (a.summary or '').startswith('დასამტკიცებელია')
        ).action_feedback(feedback=feedback)

    def action_sh_hr_approve(self):
        self._sh_hr_check_director()
        config = self.env['steelhouse.hr.task.config']._sh_get()
        for task in self:
            task.sudo().write({'sh_hr_state': 'approved'})
            task._sh_hr_move('in_progress')
            task._sh_hr_close_activities(_("დამტკიცებულია"))
            task._sh_hr_make_subtasks(config)
            task.message_post(body=_("დირექტორმა დაამტკიცა (%s).", self.env.user.name),
                              partner_ids=config.hr_manager_ids.partner_id.ids)
        return True

    def action_sh_hr_refuse(self):
        self._sh_hr_check_director()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'steelhouse.hr.refuse.wizard', 'view_mode': 'form',
            'target': 'new', 'name': _("უარყოფა"), 'context': {'default_task_id': self.id},
        }

    def _sh_hr_refuse(self, reason):
        self._sh_hr_check_director()
        config = self.env['steelhouse.hr.task.config']._sh_get()
        for task in self:
            task.sudo().write({'sh_hr_state': 'refused', 'sh_hr_refuse_reason': reason})
            task._sh_hr_move('cancelled')
            task._sh_hr_close_activities(_("უარყოფილია"))
            task.message_post(body=Markup(_("დირექტორმა უარყო. მიზეზი: <b>%s</b>")) % reason,
                              partner_ids=(config.hr_manager_ids.partner_id | task.create_uid.partner_id).ids)
        return True

    def action_sh_hr_payment(self):
        """Vacancy, after the approval: the posting is being paid for."""
        for task in self:
            if not task.sh_hr_is_manager:
                raise UserError(_("„გადახდაში“ გადაყავს HR მენეჯერს."))
            if task.sh_hr_kind != 'vacancy' or task.sh_hr_state != 'approved':
                raise UserError(_("„გადახდაში“ - მხოლოდ დამტკიცებული ვაკანსია."))
            task.sudo().write({'sh_hr_state': 'payment'})
        return True

    # ------------------------------------------------------------------ after the approval
    def _sh_hr_make_subtasks(self, config):
        """The sub-tasks of this process from the settings („ქვედავალებები“: name + the people chosen there),
        except the ones HR marked „არ არის საჭირო“ on the request. Their people follow the request."""
        self.ensure_one()
        whom = self.sh_hr_position or self.name
        rules = config.sudo().subtask_ids.filtered(lambda r: r.kind == self.sh_hr_kind and r.active) - self.sh_hr_skip_rule_ids
        viewers = self.env['res.users']
        missing = []
        for rule in rules.sorted('sequence'):
            users = rule.user_ids
            name = '%s - %s' % (rule.name, whom)
            if not users:
                missing.append(name)
                continue
            viewers |= users
            self.env['project.task'].sudo().create({
                'name': name, 'parent_id': self.id, 'project_id': self.project_id.id,
                'user_ids': [(6, 0, users.ids)], 'reviewer_ids': [(6, 0, (config.hr_manager_ids or self.reviewer_ids).ids)],
                'date_deadline': self.date_deadline,
            })
        if viewers:
            self.sudo().write({'sh_extra_viewer_ids': [(4, u.id) for u in viewers]})
            self.sudo().message_subscribe(partner_ids=viewers.partner_id.ids)
        if missing:
            self.message_post(body=_("ქვედავალება ვერ შეიქმნა - პარამეტრებში ადამიანი არ არის მითითებული: %s",
                                     '; '.join(missing)))
