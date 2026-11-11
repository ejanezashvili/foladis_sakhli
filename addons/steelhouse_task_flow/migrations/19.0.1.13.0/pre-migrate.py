def migrate(cr, version):
    """reviewer_id (one) -> reviewer_ids (several): copy the current reviewer before the ORM
    turns reviewer_id into a field computed from reviewer_ids."""
    cr.execute("""
        CREATE TABLE IF NOT EXISTS sh_task_reviewer_rel (
            task_id integer NOT NULL REFERENCES project_task(id) ON DELETE CASCADE,
            user_id integer NOT NULL REFERENCES res_users(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, user_id))
    """)
    cr.execute("""
        INSERT INTO sh_task_reviewer_rel (task_id, user_id)
        SELECT id, reviewer_id FROM project_task WHERE reviewer_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
