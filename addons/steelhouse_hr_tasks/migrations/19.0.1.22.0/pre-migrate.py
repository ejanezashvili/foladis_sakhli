"""Request templates (D-14): the fields and the sub-tasks of a process point to its template (kind_id) - filled
from the old process code before the ORM adds the column (the sub-task's one is required)."""


def migrate(cr, version):
    for table in ('steelhouse_hr_field', 'steelhouse_hr_subtask_rule'):
        cr.execute('ALTER TABLE %s ADD COLUMN IF NOT EXISTS kind_id integer' % table)
        cr.execute('UPDATE %s t SET kind_id = k.id FROM steelhouse_hr_kind k '
                   'WHERE k.kind = t.kind AND t.kind_id IS NULL' % table)
