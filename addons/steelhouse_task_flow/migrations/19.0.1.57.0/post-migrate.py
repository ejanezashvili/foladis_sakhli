def migrate(cr, version):
    """Tasks already overdue before this version get no "overdue" message - only new ones from now on."""
    cr.execute("""
        UPDATE project_task SET sh_overdue_notified = TRUE
         WHERE date_deadline IS NOT NULL AND date_deadline < (now() AT TIME ZONE 'UTC')
           AND state NOT IN ('1_done', '1_canceled')
    """)
