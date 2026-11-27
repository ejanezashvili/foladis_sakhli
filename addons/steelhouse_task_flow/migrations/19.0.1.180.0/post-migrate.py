import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """1. „მიღებული“ and „მიმდინარე“ become one step: tasks standing in a "მიღებული" stage move to
          the "მიმდინარე" stage of their department, and the emptied "მიღებული" stages are archived
          (not deleted - setting them active again brings the column back).
       2. „სამუშაოს დაწყება“ of tasks accepted before this version: the day of the first acceptance
          (Tbilisi time), where the field is empty. Repeating originals and templates are left as they are."""
    cr.execute("""
        UPDATE project_task t
           SET stage_id = (SELECT s.id
                             FROM project_task_type s
                             JOIN project_task_type_rel r ON r.type_id = s.id
                            WHERE r.project_id = t.project_id AND s.sh_kind = 'in_progress' AND s.active
                            ORDER BY s.sequence, s.id
                            LIMIT 1)
         WHERE t.stage_id IN (SELECT id FROM project_task_type WHERE sh_kind = 'accepted')
           AND EXISTS (SELECT 1
                         FROM project_task_type s
                         JOIN project_task_type_rel r ON r.type_id = s.id
                        WHERE r.project_id = t.project_id AND s.sh_kind = 'in_progress' AND s.active)
    """)
    moved = cr.rowcount
    cr.execute("""
        UPDATE project_task_type s
           SET active = FALSE
         WHERE s.sh_kind = 'accepted'
           AND NOT EXISTS (SELECT 1 FROM project_task t WHERE t.stage_id = s.id)
    """)
    archived = cr.rowcount
    cr.execute("""
        UPDATE project_task
           SET sh_work_start = (sh_wt_first AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Tbilisi')::date
         WHERE sh_work_start IS NULL
           AND sh_wt_first IS NOT NULL
           AND COALESCE(sh_repeat, FALSE) = FALSE
           AND COALESCE(is_template, FALSE) = FALSE
    """)
    _logger.info("steelhouse_task_flow 180: %s tasks moved to in_progress, %s accepted stages archived, "
                 "%s work start dates filled", moved, archived, cr.rowcount)
