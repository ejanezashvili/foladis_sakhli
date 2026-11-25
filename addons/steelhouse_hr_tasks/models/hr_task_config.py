"""„კადრები → პარამეტრები“: who does what in the HR processes - chosen here, not fixed in code (owner, 2026-11-25).
One settings record (`_sh_get`) + the list of legal entities with their accountant(s) and lawyer(s)."""
from odoo import api, fields, models

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
    timekeeping_user_ids = fields.Many2many(
        'res.users', 'sh_hrt_cfg_time_rel', 'cfg_id', 'user_id', string='დროის აღრიცხვა', domain=USERS,
        help="ახალი თანამშრომლის რეგისტრაცია დროის აღრიცხვის სისტემაში - ქვედავალება.")
    security_user_ids = fields.Many2many(
        'res.users', 'sh_hrt_cfg_sec_rel', 'cfg_id', 'user_id', string='შიდა უსაფრთხოების სამსახური', domain=USERS,
        help="გათავისუფლებისას - ქვედავალება (თუ მონიშნულია).")
    legal_entity_ids = fields.One2many('steelhouse.legal.entity', 'config_id', string='იურიდიული პირები')

    @api.model
    def _sh_get(self):
        config = self.sudo().search([], limit=1)
        return config or self.sudo().create({})

    @api.model
    def action_sh_open(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self._sh_get().id,
            'view_mode': 'form', 'target': 'current', 'name': 'კადრები - პარამეტრები',
        }


class SteelhouseLegalEntity(models.Model):
    _name = 'steelhouse.legal.entity'
    _description = 'იურიდიული პირი (კადრები)'
    _order = 'sequence, name'

    config_id = fields.Many2one('steelhouse.hr.task.config', ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    sequence = fields.Integer(default=10)
    name = fields.Char('იურიდიული პირი', required=True)
    code = fields.Char('ორგანიზაციის კოდი')
    accountant_ids = fields.Many2many('res.users', 'sh_legal_accountant_rel', 'entity_id', 'user_id',
                                      string='ბუღალტერი', domain=USERS)
    lawyer_ids = fields.Many2many('res.users', 'sh_legal_lawyer_rel', 'entity_id', 'user_id',
                                  string='იურისტი', domain=USERS)
    active = fields.Boolean(default=True)
