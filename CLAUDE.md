<!-- last-synced: 2026-11-26, commit: f9478f0 -->
# ფოლადის სახლი - task management on Odoo 19

## Stack
- Odoo 19.0 Community, on-premise (systemd service `odoo`, no Docker, no odoo.sh, no Studio).
- Server `http://146.255.249.126`, one database `steelhouse` (no dbfilter - never create a second database).
- Config `/etc/odoo/odoo.conf`, custom modules `/opt/odoo/custom-addons`, PostgreSQL on the same host.
- No local or staging instance: changes are verified on the live server (D-7). No automated tests (D-8).
- Local tools used by scripts: Python 3.12, `paramiko` (SSH), `playwright` + `ffmpeg` (video manuals).

## Commands
Run on the server (SSH over the VPN only; address and account are not kept in the repo), with sudo:
```bash
# backup before any upgrade
sudo -u postgres pg_dump -Fc steelhouse > /var/backups/odoo/steelhouse_$(date +%Y%m%d_%H%M)_before_<what>.dump
# upgrade a module (service stopped; a clean run prints no ERROR / CRITICAL line)
systemctl stop odoo
sudo -u odoo /usr/bin/odoo --config /etc/odoo/odoo.conf -d steelhouse -u steelhouse_task_flow --stop-after-init --no-http --logfile=/tmp/up.log
systemctl start odoo
# a script in the Odoo shell (deploy/*.py)
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d steelhouse --no-http < script.py
# service state / installed versions
systemctl is-active odoo
sudo -u postgres psql -At steelhouse -c "select name, latest_version from ir_module_module where name like 'steelhouse%'"
```
Local:
```powershell
# record a video manual (-Fast = trial run, screenshots only)
powershell -File deploy\manual_video\run.ps1 v4_sequence.py -Fast
```
- After a front-end change: download the backend JS bundle (follow the redirect, whole file) and `node --check` it.
- Tests, lint: none configured.

## Layout
- `addons/steelhouse_task_flow` - tasks: stages, review, sequences, boards, reports (installed).
- `addons/steelhouse_hr` - structure, several equal heads, time off (installed).
- `addons/steelhouse_hr_tasks` - HR processes „კადრები“ on top of task_flow (installed; task_flow files not edited).
- `addons/steelhouse_project` - earlier task module, not installed (status: see PLAN open questions).
- `addons/oca/` - OCA `auditlog`, `web_responsive` (installed, upstream code - do not edit).
- `deploy/` - one-off Odoo shell scripts (`setup_*.py`), `backup/`, `manual_video/`, `https/` (prepared, off).
- `i18n/ka/` - Georgian `.po` files of standard Odoo modules (loaded by `deploy/apply_ka_translations.sh`).
- `Docs/` - requirements, plan, specs, user manuals, video manuals.

## Conventions
- Field prefix `sh_` on inherited models; new models `steelhouse.<entity>` (older: `sh.<entity>`).
- XML ids: `view_<model>_<kind>_sh_<topic>`, `rule_sh_<topic>`, `ir_cron_sh_<topic>`, `action_sh_<topic>`, `menu_sh_<topic>`.
- CSS classes `o_sh_<topic>`; JS in `static/src/<topic>/` (one folder per widget: js + xml + scss).
- One topic = one file `models/task_<topic>.py` extending `project.task`, with a module docstring that says the rule.
- UI strings are written in Georgian in the source (no `.po` for the custom modules).
- Version `19.0.1.<n>.0`: bump `<n>` on every deploy; teammates bump too - check `git pull` first.
- Data change on upgrade: `migrations/<version>/post-migrate.py`.
- Commits: `feat|fix|chore|docs(<module>): <what changed, in English> (<version>)`.

## Rules (MUST / NEVER)
- STANDARD FIRST: before custom code, check standard Odoo (settings, existing fields, groups, record rules,
  automated actions) and OCA. Custom code only after naming the standard feature checked, stating why it
  does not fit, and the owner's confirmation - recorded as `D-<n>` in `Docs/DECISIONS.md`.
  Order: configuration -> automated action -> OCA module -> inherit and extend -> new model.
- NEVER edit core or OCA addons - inherit.
- ALWAYS add an `ir.model.access.csv` row for a new model.
- ALWAYS use `_inherit` unless a new table is needed.
- NEVER hardcode company ids or record ids.
- NEVER commit passwords, tokens, personal data (`.gitignore`: `Docs/HR/`, password files, employee lists).
- ALWAYS declare every field a kanban card template reads (`<field name=... invisible="1"/>`).
- Kanban cards on the employee's board: pick a card by `.o_sh_card_title`, not by text.

## Workflow
PRD -> SPEC -> PLAN -> code -> check on the live server -> `/docs-sync`.
`Docs/PLAN.md` must be approved by the owner before implementation starts.

## Docs map
- `README.md` - what each module adds, version by version (Georgian); the detailed change log.
- `Docs/გეგმა.md` - rollout plan by stages, requirements map, history of done work.
- `Docs/PRD.md` - problem, roles, user stories, acceptance criteria.
- `Docs/SPEC.md` - data model, rules, views, security, jobs.
- `Docs/PLAN.md` - remaining work only.
- `Docs/ARCHITECTURE.md` - components, data flow, extension points.
- `Docs/DECISIONS.md` - ADR list (`D-<n>`).
- `addons/<module>/README.md` - purpose, install, configuration, limits.
- `Docs/ვიდეო მანუალები/` - four video manuals (mp4, not in git).
