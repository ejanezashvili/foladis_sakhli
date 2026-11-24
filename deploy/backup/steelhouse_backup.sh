#!/bin/sh
# 8.5 nightly backup of the Odoo database "steelhouse" + its filestore.
# Installed as /usr/local/bin/steelhouse_backup.sh, run by /etc/cron.d/steelhouse-backup (root, 02:00).
# Keeps: the last 14 daily copies + the copy of the 1st of each month for 12 months.
set -eu

DB=steelhouse
DIR=/var/backups/odoo/auto
FILESTORE=/var/lib/odoo/.local/share/Odoo/filestore/$DB
LOG=/var/log/steelhouse_backup.log
STAMP=$(date +%Y%m%d_%H%M)
KIND=daily
[ "$(date +%d)" = "01" ] && KIND=monthly

mkdir -p "$DIR"
chmod 700 "$DIR"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

DUMP="$DIR/${DB}_${KIND}_${STAMP}.dump"
FILES="$DIR/${DB}_${KIND}_${STAMP}_filestore.tar.gz"

if ! sudo -u postgres pg_dump -Fc "$DB" > "$DUMP.part"; then
    log "ERROR pg_dump failed"
    rm -f "$DUMP.part"
    exit 1
fi
mv "$DUMP.part" "$DUMP"
# the dump must be readable (a broken file is worse than none)
if ! pg_restore -l "$DUMP" > /dev/null 2>&1; then
    log "ERROR dump not readable: $DUMP"
    exit 1
fi
tar -czf "$FILES" -C "$(dirname "$FILESTORE")" "$DB"
chmod 600 "$DUMP" "$FILES"

# rotation
find "$DIR" -name "${DB}_daily_*" -mtime +14 -delete
find "$DIR" -name "${DB}_monthly_*" -mtime +370 -delete

log "OK $(basename "$DUMP") $(du -h "$DUMP" | cut -f1), filestore $(du -h "$FILES" | cut -f1)"
