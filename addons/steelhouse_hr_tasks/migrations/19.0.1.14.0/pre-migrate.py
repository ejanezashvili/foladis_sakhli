"""Sub-tasks go to chosen people only (owner, 2026-11-26): the rules that took the legal entity's lawyer /
accountant get those people as chosen ones; the entity's lawyer / accountant lists are dropped after this."""


def migrate(cr, version):
    for kind, rel in (('lawyer', 'sh_legal_lawyer_rel'), ('accountant', 'sh_legal_accountant_rel')):
        cr.execute("SELECT to_regclass(%s)", (rel,))
        if cr.fetchone()[0]:
            cr.execute("""
                INSERT INTO sh_hrt_subtask_rule_user_rel (rule_id, user_id)
                SELECT DISTINCT r.id, x.user_id FROM steelhouse_hr_subtask_rule r, {rel} x
                 WHERE r.assignee = %s
                ON CONFLICT DO NOTHING
            """.format(rel=rel), (kind,))
        cr.execute("UPDATE steelhouse_hr_subtask_rule SET assignee = 'users' WHERE assignee = %s", (kind,))
