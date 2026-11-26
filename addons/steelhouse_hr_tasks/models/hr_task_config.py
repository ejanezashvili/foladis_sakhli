"""„კადრები → პარამეტრები“: who does what in the HR processes, which fields are required and which sub-tasks
are made after the director's approval - all set by HR here, not in code (owner, 2026-11-25 / 2026-11-26).
One settings record (`_sh_get`), the legal entities (name + organisation code), the sub-task list."""
from odoo import api, fields, models

from .hr_constants import ASSIGNEES, CANDIDATES, DEFAULT_REQUIRED, KINDS

USERS = "[('share', '=', False)]"


class SteelhouseHrTaskConfig(models.Model):
    _name = 'steelhouse.hr.task.config'
    _description = 'კადრების პროცესების პარამეტრები'

    name = fields.Char(default='კადრების პროცესები', readonly=True)
    hr_manager_ids = fields.Many2many(
        'res.users', 'sh_hrt_cfg_hr_rel', 'cfg_id', 'user_id', string='HR მენეჯერი', domain=USERS,
        help="ამოწმებს მოთხოვნას და დირექტორს უგზავნის; ხდება შემსრულებელი და შემმოწმებელი.")
    director_id = fields.Many2one(
        'res.users', string='დირექტორი (ამტკიცებს)', domain=USERS,
        help="მხოლოდ ის ამტკიცებს ან უარყოფს ვაკანსიას, აყვანას და გათავისუფლებას.")
    # kept for the first filling of the sub-task list (19.0.1.10.0) - the list is used since then
    timekeeping_user_ids = fields.Many2many(
        'res.users', 'sh_hrt_cfg_time_rel', 'cfg_id', 'user_id', string='დროის აღრიცხვა', domain=USERS)
    security_user_ids = fields.Many2many(
        'res.users', 'sh_hrt_cfg_sec_rel', 'cfg_id', 'user_id', string='შიდა უსაფრთხოების სამსახური', domain=USERS)
    legal_entity_ids = fields.One2many('steelhouse.legal.entity', 'config_id', string='იურიდიული პირები')

    vacancy_field_ids = fields.Many2many(
        'steelhouse.hr.field', 'sh_hrt_cfg_reqf_vacancy_rel', 'cfg_id', 'field_id', string='ვაკანსია - სავალდებულო ველები',
        domain=[('kind', '=', 'vacancy')])
    hire_field_ids = fields.Many2many(
        'steelhouse.hr.field', 'sh_hrt_cfg_reqf_hire_rel', 'cfg_id', 'field_id', string='აყვანა - სავალდებულო ველები',
        domain=[('kind', '=', 'hire')])
    dismissal_field_ids = fields.Many2many(
        'steelhouse.hr.field', 'sh_hrt_cfg_reqf_dismissal_rel', 'cfg_id', 'field_id', string='გათავისუფლება - სავალდებულო ველები',
        domain=[('kind', '=', 'dismissal')])

    subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'config_id', string='ქვედავალებები')
    vacancy_subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'config_id', domain=[('kind', '=', 'vacancy')],
                                          context={'default_kind': 'vacancy'}, string='ვაკანსია - ქვედავალებები')
    hire_subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'config_id', domain=[('kind', '=', 'hire')],
                                       context={'default_kind': 'hire'}, string='აყვანა - ქვედავალებები')
    dismissal_subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'config_id',
                                            domain=[('kind', '=', 'dismissal')], context={'default_kind': 'dismissal'},
                                            string='გათავისუფლება - ქვედავალებები')

    @api.model
    def _sh_get(self):
        config = self.sudo().search([], limit=1)
        return config or self.sudo().create({})

    def _sh_required(self, kind):
        """Names of the required fields of a process."""
        return (self['%s_field_ids' % kind].mapped('fname') if kind in CANDIDATES else [])

    @api.model
    def _sh_defaults(self):
        """First filling (install / upgrade to 19.0.1.10.0): the client's documents - only where still empty."""
        config = self._sh_get()
        Field = self.env['steelhouse.hr.field'].sudo()
        task_fields = self.env['project.task']._fields
        for kind, names in CANDIDATES.items():
            for seq, fname in enumerate(names):
                if not Field.search_count([('kind', '=', kind), ('fname', '=', fname)]):
                    Field.create({'kind': kind, 'fname': fname, 'sequence': seq, 'name': task_fields[fname].string})
        for kind, names in DEFAULT_REQUIRED.items():
            if not config['%s_field_ids' % kind]:
                config['%s_field_ids' % kind] = [(6, 0, Field.search([('kind', '=', kind), ('fname', 'in', names)]).ids)]
        if not config.subtask_ids:
            rules = [
                ('hire', 10, 'დოკუმენტების მომზადება', 'users', False, False),
                ('hire', 20, 'დროის აღრიცხვის სისტემაში რეგისტრაცია', 'users', config.timekeeping_user_ids, False),
                ('hire', 30, 'RS.ge-ზე რეგისტრაცია', 'users', False, False),
                ('dismissal', 10, 'გათავისუფლების დოკუმენტები', 'users', False, True),
                ('dismissal', 20, 'RS.ge - გათავისუფლება', 'users', False, True),
                ('dismissal', 30, 'შიდა უსაფრთხოება - გათავისუფლება', 'users', config.security_user_ids, True),
            ]
            self.env['steelhouse.hr.subtask.rule'].sudo().create([{
                'config_id': config.id, 'kind': kind, 'sequence': seq, 'name': name, 'assignee': assignee,
                'user_ids': [(6, 0, users.ids)] if users else False, 'optional': optional,
            } for kind, seq, name, assignee, users, optional in rules])
        return config

    @api.model
    def action_sh_open(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self._sh_get().id,
            'view_mode': 'form', 'target': 'current', 'name': 'კადრები - პარამეტრები',
        }


class SteelhouseHrSubtaskRule(models.Model):
    _name = 'steelhouse.hr.subtask.rule'
    _description = 'კადრების პროცესის ქვედავალება (პარამეტრები)'
    _order = 'kind, sequence, id'

    config_id = fields.Many2one('steelhouse.hr.task.config', required=True, ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    kind = fields.Selection(KINDS, string='პროცესი', required=True)
    sequence = fields.Integer(default=10)
    name = fields.Char('ქვედავალება', required=True, help="სათაური; ბოლოში ემატება თანამდებობა / მოთხოვნის სახელი.")
    assignee = fields.Selection(ASSIGNEES, string='ვის ეწერება', required=True, default='users')
    user_ids = fields.Many2many('res.users', 'sh_hrt_subtask_rule_user_rel', 'rule_id', 'user_id',
                                string='ადამიანები', domain=USERS,
                                help="როცა „ვის ეწერება“ = „არჩეული ადამიანები“.")
    optional = fields.Boolean('მოთხოვნაზე შეიძლება გამოტოვება',
                              help="HR მოთხოვნაზე მონიშნავს „არ არის საჭირო“ - ეს ქვედავალება არ შეიქმნება.")
    active = fields.Boolean(default=True)


class SteelhouseLegalEntity(models.Model):
    _name = 'steelhouse.legal.entity'
    _description = 'იურიდიული პირი (კადრები)'
    _order = 'sequence, name'

    config_id = fields.Many2one('steelhouse.hr.task.config', ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    sequence = fields.Integer(default=10)
    name = fields.Char('იურიდიული პირი', required=True)
    code = fields.Char('ორგანიზაციის კოდი')
    active = fields.Boolean(default=True)


class SteelhouseHrField(models.Model):
    """The fields a process shows on the form (filled by the module) - HR ticks which ones are required."""
    _name = 'steelhouse.hr.field'
    _description = 'კადრების პროცესის ველი'
    _order = 'kind, sequence, id'

    kind = fields.Selection(KINDS, string='პროცესი', required=True)
    sequence = fields.Integer(default=10)
    fname = fields.Char('ტექნიკური სახელი', required=True)
    name = fields.Char('ველი', required=True)
