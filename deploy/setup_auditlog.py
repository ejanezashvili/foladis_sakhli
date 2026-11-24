"""8.4 audit log (OCA auditlog): what is recorded - who created / changed / deleted what, with the old and
new values. Run in the Odoo shell on the server (idempotent - re-running updates the rules):

    sudo -u odoo odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < setup_auditlog.py

The log: Settings - Technical - Audit - Logs (administrators). Kept 365 days (daily clean-up job).
"""
RULES = [
    # model, name, create, write, delete, export
    ('project.task', 'დავალებები', True, True, True, True),
    ('project.project', 'პროექტები და დეპარტამენტების დაფები', True, True, True, False),
    ('res.users', 'მომხმარებლები (უფლებები, აქტივაცია)', True, True, True, True),
    ('res.groups', 'უფლებების ჯგუფები', True, True, True, False),
    ('hr.employee', 'თანამშრომლები', True, True, True, True),
    ('hr.department', 'დეპარტამენტები', True, True, True, False),
    ('hr.leave', 'შვებულებები', True, True, True, True),
    ('hr.leave.allocation', 'შვებულების დღეების მინიჭება', True, True, True, False),
    ('hr.leave.type', 'შვებულების ტიპები', True, True, True, False),
    ('base.automation', 'ავტომატიზაციის წესები', True, True, True, False),
]
KEEP_DAYS = 365
# technical fields that only add noise (the chatter itself is not audit data)
NOISE = ['message_ids', 'message_follower_ids', 'message_partner_ids', 'website_message_ids', 'activity_ids',
         'rating_ids', 'message_main_attachment_id', 'write_date', 'write_uid']

Rule = env['auditlog.rule'].sudo()
for model, name, c, w, u, e in RULES:
    ir_model = env['ir.model'].sudo().search([('model', '=', model)], limit=1)
    if not ir_model:
        print('AUDIT skip (no model)', model)
        continue
    vals = {'name': name, 'model_id': ir_model.id, 'log_create': c, 'log_write': w, 'log_unlink': u,
            'log_export_data': e, 'log_read': False, 'log_type': 'full', 'capture_record': False,
            'fields_to_exclude_ids': [(6, 0, env['ir.model.fields'].sudo().search(
                [('model', '=', model), ('name', 'in', NOISE)]).ids)]}
    rule = Rule.search([('model_id', '=', ir_model.id)], limit=1)
    if rule:
        if rule.state == 'confirmed':
            rule.set_to_draft()
        rule.write(vals)
    else:
        rule = Rule.create(vals)
    rule.set_to_confirmed()
    print('AUDIT rule', model, rule.state)

cron = env.ref('auditlog.ir_cron_auditlog_autovacuum').sudo()
cron.write({'active': True, 'code': 'model.autovacuum(%d)' % KEEP_DAYS})
print('AUDIT vacuum', cron.active, cron.code)
env.cr.commit()
