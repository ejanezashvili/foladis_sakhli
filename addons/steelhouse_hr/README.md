<!-- last-synced: 2026-11-25, commit: c56cf43 -->
# steelhouse_hr

Company structure and time off for ფოლადის სახლი on Odoo 19.0 Community: several equal heads of a department, org chart and hierarchy views, time off with deputies, approval order, balance per quarter and a report.
Installed on the live server, version 19.0.1.64.0.

## Dependencies
`hr`, `hr_org_chart`, `web_hierarchy`, `hr_holidays`, `mail`.

## Install / upgrade
Same steps as `steelhouse_task_flow` (backup, copy, `-u steelhouse_hr --stop-after-init`, clean log, start). Upgrade this module before `steelhouse_task_flow`, which depends on it.

## Configuration
- Heads: Employees → Departments, field „ხელმძღვანელები“ (`manager_ids`).
- Structure data: `deploy/setup_structure*.py` (Odoo shell).
- Public holidays: `deploy/holidays_2026.py`.
- Groups: none of its own; time off officers are `hr_holidays.group_hr_holidays_user`.
- Scheduled jobs: `cron_sync_leave_approvals` (hourly), `cron_quarter_allocations` (daily), `cron_mandatory_days_monthly` (daily).
- Record rules: `rule_leave_balance_own`, `rule_leave_balance_officer`, `rule_hr_leave_co_head`, `rule_hr_leave_allocation_co_head_read`, `rule_hr_leave_deputy_read`.

## Known limitations
- No automated tests.
- Overrides two routes of the `hr_org_chart` controller - re-check after an Odoo update.
- UI strings are Georgian in the source.

## Docs
`../../README.md` (change log), `../../Docs/SPEC.md`, user manual `../../Docs/შვებულების მოდული - სახელმძღვანელო.docx` (+ pdf).
