from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Confidentiality is gone, "დამატებით ხედავენ" stays as a field of its own: the people who were
    let in to a confidential task keep seeing it."""
    cr.execute("SELECT to_regclass('sh_task_confidential_viewer_rel')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        INSERT INTO sh_task_extra_viewer_rel (task_id, user_id)
        SELECT old.task_id, old.user_id
          FROM sh_task_confidential_viewer_rel old
          JOIN project_task t ON t.id = old.task_id
          JOIN res_users u ON u.id = old.user_id
        ON CONFLICT DO NOTHING
        RETURNING task_id
    """)
    ids = list({row[0] for row in cr.fetchall()})
    if ids:
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['project.task'].invalidate_model(['sh_extra_viewer_ids'])
        env['project.task'].browse(ids)._sh_sync_party()
