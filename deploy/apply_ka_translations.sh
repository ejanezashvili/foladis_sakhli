#!/bin/sh
# Copies our Georgian translations (i18n/ka/<module>.po) into Odoo's addons.
# Run on the server with sudo:  sudo sh apply_ka_translations.sh /path/to/i18n/ka
# Re-run after every Odoo package upgrade (the upgrade overwrites these files).
# Then reload: Settings > Translations > Languages > Georgian > Update (overwrite), or restart + reload.
set -e
SRC="$1"
ADDONS=/usr/lib/python3/dist-packages/odoo/addons
BACKUP=/var/backups/odoo/i18n_orig
mkdir -p "$BACKUP"
for f in "$SRC"/*.po; do
    mod=$(basename "$f" .po)
    [ -d "$ADDONS/$mod/i18n" ] || { echo "skip $mod (not found)"; continue; }
    if [ ! -e "$BACKUP/$mod.ka.po" ] && [ ! -e "$BACKUP/$mod.ka.po.none" ]; then
        if [ -f "$ADDONS/$mod/i18n/ka.po" ]; then cp "$ADDONS/$mod/i18n/ka.po" "$BACKUP/$mod.ka.po"; else touch "$BACKUP/$mod.ka.po.none"; fi
    fi
    install -m 644 "$f" "$ADDONS/$mod/i18n/ka.po"
    echo "ok $mod"
done
