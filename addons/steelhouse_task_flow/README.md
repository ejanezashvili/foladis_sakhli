<!-- last-synced: 2026-11-26, commit: f9478f0 -->
# steelhouse_task_flow

Task management for ფოლადის სახლი on Odoo 19.0 Community: stages with a fixed meaning, review by the author, sequences of steps across departments, hold / resume, visibility by a list, boards, home page, approvals app, reports.
Installed on the live server, version 19.0.1.179.0 (179: phone layout fixes, `static/src/mobile/mobile.scss`).
`steelhouse_hr_tasks` builds on this module (stage kinds, `_sh_stage_of_kind`, `sh_extra_viewer_ids`, reason windows) - tell before changing them.

## Dependencies
`project`, `hr`, `steelhouse_hr`.

## Install / upgrade
1. Back up the database (`pg_dump -Fc steelhouse`), keep a copy of the current module folder.
2. Copy the module to `/opt/odoo/custom-addons/steelhouse_task_flow` (owner `odoo`).
3. `systemctl stop odoo`, then `odoo --config /etc/odoo/odoo.conf -d steelhouse -u steelhouse_task_flow --stop-after-init --no-http --logfile=<log>`.
4. The log must have no `ERROR` / `CRITICAL` line; otherwise put the old folder back.
5. `systemctl start odoo`; after a front-end change check the JS bundle with `node --check`.

## Configuration
- Stage meaning: Project → Configuration → Stages, field `sh_kind` on every stage.
- Who sees whose tasks: Project → Configuration → „დავალებების ხილვა“ (system administrators only). Initial list: `deploy/setup_task_visibility.py`.
- Groups: none of its own. Project administrators (`project.group_project_manager`) see and change everything.
- Scheduled jobs: `ir_cron_sh_repeat` (hourly), `ir_cron_sh_overdue_notify` (hourly), `ir_cron_sh_weekly_digest` (daily), `ir_cron_sh_place_personal` (daily).
- Department boards: a `project.project` with `sh_is_department` and `sh_department_id`.

## Known limitations
- No automated tests; checked by hand on the live server.
- Notifications go to Discuss only (no SMTP on the server).
- The next step can be allowed to start only when the previous one is on hold; "დაწყების მოთხოვნა" only notifies.
- The sequence diagram shows at most 80 tasks.
- A task's performer can edit the whole sequence of his task (the tab is read-only only without write access).
- UI strings are Georgian in the source; there is no translation file.

## Docs
`../../README.md` (change log), `../../Docs/SPEC.md`, `../../Docs/ARCHITECTURE.md`, `../../Docs/DECISIONS.md`, video manuals in `../../Docs/ვიდეო მანუალები/`.
