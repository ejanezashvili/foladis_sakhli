#!/bin/sh
# 8.5 restore test: the newest automatic backup is restored into a separate database
# "steelhouse_restore_test", a few counts are compared with the live database, then it is dropped.
# The live database is never touched. Installed as /usr/local/bin/steelhouse_restore_test.sh,
# run monthly by /etc/cron.d/steelhouse-backup (and by hand: sudo steelhouse_restore_test.sh).
set -eu

DB=steelhouse
TEST=steelhouse_restore_test
DIR=/var/backups/odoo/auto
LOG=/var/log/steelhouse_backup.log
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

DUMP=$(ls -t "$DIR"/${DB}_*.dump 2>/dev/null | head -1)
[ -n "$DUMP" ] || { log "RESTORE-TEST ERROR no backup in $DIR"; exit 1; }

psql_q() { sudo -u postgres psql -Atc "$2" "$1"; }
sudo -u postgres dropdb --if-exists --force "$TEST"
# owned by postgres and closed to everyone else: the running Odoo (user "odoo") looks at every
# database it may open and would start its scheduled jobs on the copy
sudo -u postgres createdb "$TEST"
sudo -u postgres psql -qc "REVOKE CONNECT ON DATABASE $TEST FROM PUBLIC" postgres
# the backup files are root-only: root reads the file and hands it to pg_restore
if ! sudo -u postgres pg_restore --no-owner --no-privileges -d "$TEST" < "$DUMP" > /tmp/steelhouse_restore_test.err 2>&1; then
    log "RESTORE-TEST WARNING pg_restore errors for $(basename "$DUMP"): $(tail -c 300 /tmp/steelhouse_restore_test.err | tr '\n' ' ')"
fi

Q="select (select count(*) from project_task)||'/'||(select count(*) from hr_employee)||'/'||(select count(*) from res_users)||'/'||(select count(*) from hr_leave)"
LIVE=$(psql_q "$DB" "$Q")
RESTORED=$(psql_q "$TEST" "$Q" || echo "FAILED")
sudo -u postgres dropdb --force "$TEST"
[ "$RESTORED" != "FAILED" ] || { log "RESTORE-TEST ERROR $(basename "$DUMP") could not be restored"; exit 1; }

# counts: tasks / employees / users / time off; the live ones may have grown since the backup
log "RESTORE-TEST $(basename "$DUMP"): restored $RESTORED, live now $LIVE"
