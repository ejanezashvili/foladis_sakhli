"""„კადრები → პარამეტრები“: who does what in the HR processes, which fields are required and which sub-tasks
are made after the director's approval - all set by HR here, not in code (owner, 2026-11-25 / 2026-11-26).
One settings record (`_sh_get`), the legal entities (name + organisation code), the sub-task list."""
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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

    subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'config_id', string='ქვედავალებები')
    # the request templates (the three built-in ones + the ones HR creates) - each one is a menu item
    kind_ids = fields.One2many('steelhouse.hr.kind', 'config_id', string='შაბლონები', context={'active_test': False})
    # the settings page shows one template at a time - one tab per template (made in _get_view), as the old tabs
    # ვაკანსია / აყვანა / გათავისუფლება; empty = the tab „ადამიანები“. A tab saves the form before switching.
    kind_id = fields.Many2one('steelhouse.hr.kind', string='შაბლონი', ondelete='set null')
    kind_required_field_ids = fields.Many2many(related='kind_id.required_field_ids', readonly=False,
                                               string='სავალდებულო ველები', domain=[])
    kind_subtask_ids = fields.One2many(related='kind_id.subtask_ids', readonly=False, string='ქვედავალებები')
    kind_is_builtin = fields.Boolean(related='kind_id.is_builtin')

    @api.model
    def _sh_get(self):
        config = self.sudo().search([], limit=1)
        return config or self.sudo().create({})

    def _sh_kind(self, kind):
        Kind = self.env['steelhouse.hr.kind'].sudo().with_context(active_test=False)
        return Kind.search([('kind', '=', kind)], limit=1) if kind else Kind

    def _sh_required(self, kind):
        """Names of the required built-in fields of a process."""
        return self._sh_kind(kind).required_field_ids.filtered('fname').mapped('fname')

    def _sh_required_extra(self, kind):
        """Required fields HR created himself (kept as properties of the request); a yes / no one cannot be."""
        return self._sh_kind(kind).required_field_ids.filtered(lambda f: f.pname and f.ftype != 'boolean')

    @api.model
    def _sh_defaults(self):
        """First filling (install / upgrade): the client's documents - only where still empty. The built-in
        templates are linked to their menu items of the XML (19.0.1.22.0)."""
        config = self._sh_get()
        Kind = self.env['steelhouse.hr.kind'].sudo().with_context(active_test=False)
        Field = self.env['steelhouse.hr.field'].sudo()
        task_fields = self.env['project.task']._fields
        for seq, (kind, label) in enumerate(KINDS, start=1):
            rec = Kind.search([('kind', '=', kind)], limit=1)
            new = not rec
            if new:
                rec = Kind.create({'kind': kind, 'name': label, 'sequence': seq, 'config_id': config.id})
            if not rec.config_id:
                rec.config_id = config
            if not rec.menu_id:
                rec.write({'menu_id': self.env.ref('steelhouse_hr_tasks.menu_sh_hr_new_%s' % kind).id,
                           'action_id': self.env.ref('steelhouse_hr_tasks.action_sh_hr_new_%s' % kind).id})
            for fseq, fname in enumerate(CANDIDATES[kind]):
                if not Field.search_count([('kind_id', '=', rec.id), ('fname', '=', fname)]):
                    Field.create({'kind_id': rec.id, 'fname': fname, 'sequence': fseq,
                                  'name': task_fields[fname].string})
            if new:
                rec.required_field_ids = Field.search(
                    [('kind_id', '=', rec.id), ('fname', 'in', DEFAULT_REQUIRED[kind])])
        if not config.subtask_ids:
            rules = [
                ('hire', 10, 'დოკუმენტების მომზადება', 'users', False, False),
                ('hire', 20, 'დროის აღრიცხვის სისტემაში რეგისტრაცია', 'users', config.timekeeping_user_ids, False),
                ('hire', 30, 'RS.ge-ზე რეგისტრაცია', 'users', False, False),
                ('dismissal', 10, 'გათავისუფლების დოკუმენტები', 'users', False, True),
                ('dismissal', 20, 'RS.ge - გათავისუფლება', 'users', False, True),
                ('dismissal', 30, 'შიდა უსაფრთხოება - გათავისუფლება', 'users', config.security_user_ids, True),
            ]
            kinds = {k.kind: k.id for k in Kind.search([])}
            self.env['steelhouse.hr.subtask.rule'].sudo().create([{
                'config_id': config.id, 'kind_id': kinds[kind], 'sequence': seq, 'name': name, 'assignee': assignee,
                'user_ids': [(6, 0, users.ids)] if users else False, 'optional': optional,
            } for kind, seq, name, assignee, users, optional in rules])
        return config

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """The tab line of the settings: „ადამიანები“ (in the XML) + one tab per template, in their order."""
        arch, view = super()._get_view(view_id, view_type, **options)
        for node in arch.xpath("//div[@name='sh_kind_tabs']"):
            plus = node.find("button[@name='action_sh_new_kind']")
            for kind in self.env['steelhouse.hr.kind'].sudo().search([]):
                for current in (True, False):
                    button = etree.Element('button', {
                        'name': 'action_sh_pick_kind', 'type': 'object', 'string': kind.name,
                        'context': "{'sh_kind_id': %d}" % kind.id,
                        'class': 'o_sh_kind_tab' + (' o_sh_kind_tab_on' if current else ''),
                        'invisible': ('kind_id != %d' if current else 'kind_id == %d') % kind.id})
                    if plus is not None:
                        plus.addprevious(button)
                    else:
                        node.append(button)
        return arch, view

    def action_sh_pick_kind(self):
        """A tab of the settings (the form is saved first by the button)."""
        self.ensure_one()
        self.kind_id = self.env.context.get('sh_kind_id') or False
        return True

    def action_sh_open_kind(self):
        """The template's own form: rename, archive (hides its menu item), delete."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'steelhouse.hr.kind', 'res_id': self.kind_id.id,
                'view_mode': 'form', 'target': 'current', 'name': self.kind_id.name}

    def action_sh_archive_kind(self):
        """Buttons on the template's tab (owner 2026-11-27: the ⚙ menu of the template form was not found).
        The page is reloaded: the top menu and the tab line follow at once."""
        self.ensure_one()
        kind = self.kind_id
        self.kind_id = False
        kind.active = False
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_sh_delete_kind(self):
        self.ensure_one()
        kind = self.kind_id
        self.kind_id = False
        kind.unlink()   # refused for a built-in one and for one with requests (archive it)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_sh_new_kind(self):
        return self.env['ir.actions.act_window']._for_xml_id('steelhouse_hr_tasks.action_sh_hr_new_kind')

    @api.model
    def action_sh_open(self):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self._sh_get().id,
            'view_mode': 'form', 'target': 'current', 'name': 'კადრები - პარამეტრები',
        }


class SteelhouseHrSubtaskRule(models.Model):
    _name = 'steelhouse.hr.subtask.rule'
    _description = 'კადრების პროცესის ქვედავალება (პარამეტრები)'
    _order = 'kind_id, sequence, id'

    config_id = fields.Many2one('steelhouse.hr.task.config', required=True, ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    kind_id = fields.Many2one('steelhouse.hr.kind', string='შაბლონი', required=True, ondelete='cascade', index=True)
    kind = fields.Char(related='kind_id.kind', store=True, index=True, string='პროცესი')
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


FTYPES = [('char', 'ტექსტი'), ('text', 'გრძელი ტექსტი'), ('date', 'თარიღი'), ('integer', 'რიცხვი'),
          ('boolean', 'კი / არა')]


class SteelhouseHrField(models.Model):
    """The fields of a process: the built-in ones (filled by the module, `fname`) and the ones HR creates from the
    required-fields list („შექმნა“ - `pname`, shown on the request as an Odoo property). HR ticks the required ones."""
    _name = 'steelhouse.hr.field'
    _description = 'კადრების პროცესის ველი'
    _order = 'kind_id, sequence, id'

    config_id = fields.Many2one('steelhouse.hr.task.config', ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    # empty only for a moment: a field created on a template that is not saved yet gets it on the save
    kind_id = fields.Many2one('steelhouse.hr.kind', string='შაბლონი', ondelete='cascade', index=True)
    kind = fields.Char(related='kind_id.kind', store=True, index=True, string='პროცესი')
    sequence = fields.Integer(default=50)
    fname = fields.Char('ტექნიკური სახელი', readonly=True)
    pname = fields.Char(readonly=True, copy=False)
    name = fields.Char('ველი', required=True)
    ftype = fields.Selection(FTYPES, string='ტიპი', default='char', required=True,
                             help="მხოლოდ შექმნილ ველზე; ჩაშენებულს თავისი ტიპი აქვს.")

    def _sh_kinds(self):
        return self.sudo().kind_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered(lambda r: not r.fname):
            rec.pname = 'shx%d' % rec.id
        records._sh_kinds()._sh_rebuild()
        return records

    def write(self, vals):
        if 'fname' in vals or ('ftype' in vals and self.filtered('fname')):
            vals = {k: v for k, v in vals.items() if k not in ('fname', 'ftype')} if self.filtered('fname') else vals
        kinds = self._sh_kinds()
        res = super().write(vals)
        (kinds | self._sh_kinds())._sh_rebuild()
        return res

    def action_sh_delete(self):
        """The trash button in the „ძიება“ window of the required-fields tags (created fields only)."""
        self.unlink()
        return True

    def unlink(self):
        if self.filtered('fname') and not self.env.su:
            raise UserError(_("ჩაშენებული ველი არ იშლება - მოხსენით „სავალდებულოდან“."))
        kinds = self._sh_kinds()
        res = super().unlink()
        kinds._sh_rebuild()
        return res
class SteelhouseHrKind(models.Model):
    """A request template (owner, 2026-11-27, D-14): the three built-in ones (vacancy / hire / dismissal, their
    form blocks are in the code) and the ones HR creates („კადრები → ახალი მოთხოვნა → + ახალი შაბლონი“): name,
    the fields HR creates (the request's properties), the required ones, the sub-tasks after the approval.
    Every template is a menu item of „ახალი მოთხოვნა“ (made here for a new one); archiving hides it.
    The flow is the same for all: HR -> director -> approved / refused (+ „გადახდაში“ only for the vacancy)."""
    _name = 'steelhouse.hr.kind'
    _description = 'კადრების მოთხოვნის შაბლონი'
    _order = 'sequence, id'

    kind = fields.Char('კოდი', readonly=True, copy=False, index=True)
    name = fields.Char('შაბლონი', required=True)
    sequence = fields.Integer(default=50)
    active = fields.Boolean(default=True)
    config_id = fields.Many2one('steelhouse.hr.task.config', ondelete='cascade',
                                default=lambda self: self.env['steelhouse.hr.task.config']._sh_get())
    is_builtin = fields.Boolean(compute='_compute_is_builtin')
    field_ids = fields.One2many('steelhouse.hr.field', 'kind_id', string='ველები')
    required_field_ids = fields.Many2many(
        'steelhouse.hr.field', 'sh_hr_kind_required_field_rel', 'kind_id', 'field_id', string='სავალდებულო ველები',
        domain="[('kind_id', '=', id)]")
    subtask_ids = fields.One2many('steelhouse.hr.subtask.rule', 'kind_id', string='ქვედავალებები')
    menu_id = fields.Many2one('ir.ui.menu', readonly=True, copy=False, ondelete='set null')
    action_id = fields.Many2one('ir.actions.act_window', readonly=True, copy=False, ondelete='set null')
    properties_definition = fields.PropertiesDefinition('დამატებითი ველები')

    @api.depends('kind')
    def _compute_is_builtin(self):
        for rec in self:
            rec.is_builtin = rec.kind in dict(KINDS)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.kind:
                rec.kind = 'k%d' % rec.id
            # fields created in the tags before the template was saved
            rec.required_field_ids.filtered(lambda f: not f.kind_id).sudo().kind_id = rec
        records.filtered(lambda r: not r.is_builtin and not r.menu_id)._sh_make_menu()
        records._sh_rebuild()
        self.env.registry.clear_cache('templates')   # the tabs of the settings (_get_view)
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'name', 'sequence', 'active'} & set(vals):
            self._sh_sync_menu()
            self.env.registry.clear_cache('templates')
        if 'required_field_ids' in vals:
            self._sh_rebuild()   # the * of the required ones
        return res

    def _sh_action_context(self):
        return repr({'default_sh_hr_kind': self.kind, 'default_name': self.name})

    def _sh_make_menu(self):
        parent = self.env.ref('steelhouse_hr_tasks.menu_sh_hr_new')
        for rec in self.sudo():
            action = self.env['ir.actions.act_window'].sudo().create({
                'name': rec.name, 'res_model': 'project.task', 'view_mode': 'form', 'target': 'current',
                'context': rec._sh_action_context()})
            menu = self.env['ir.ui.menu'].sudo().create({
                'name': rec.name, 'parent_id': parent.id, 'sequence': rec.sequence, 'active': rec.active,
                'action': 'ir.actions.act_window,%d' % action.id})
            super(SteelhouseHrKind, rec).write({'menu_id': menu.id, 'action_id': action.id})

    def _sh_sync_menu(self):
        for rec in self.sudo():
            if rec.menu_id:
                rec.menu_id.write({'name': rec.name, 'sequence': rec.sequence, 'active': rec.active})
            if rec.action_id and not rec.is_builtin:
                rec.action_id.write({'name': rec.name, 'context': rec._sh_action_context()})

    @api.ondelete(at_uninstall=False)
    def _sh_check_unlink(self):
        for rec in self:
            if rec.is_builtin:
                raise UserError(_("ჩაშენებული შაბლონი „%s“ არ იშლება - შეგიძლიათ დაარქივოთ.", rec.name))
            if self.env['project.task'].sudo().with_context(active_test=False).search_count(
                    [('sh_hr_kind', '=', rec.kind)], limit=1):
                raise UserError(_("„%s“-ით მოთხოვნები უკვე შექმნილია - შაბლონი არ იშლება, დაარქივეთ.", rec.name))

    def unlink(self):
        menus, actions = self.sudo().menu_id, self.sudo().action_id
        res = super().unlink()
        menus.unlink()
        actions.unlink()
        self.env.registry.clear_cache('templates')
        return res

    def _sh_rebuild(self):
        Field = self.env['steelhouse.hr.field'].sudo()
        for rec in self.sudo():
            required = rec.required_field_ids
            rec.properties_definition = [
                {'name': f.pname, 'string': f.name + (' *' if f in required and f.ftype != 'boolean' else ''),
                 'type': f.ftype}
                for f in Field.search([('kind_id', '=', rec.id), ('pname', '!=', False)], order='sequence, id')]
