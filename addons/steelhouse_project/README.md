<!-- last-synced: 2026-11-25, commit: c56cf43 -->
# steelhouse_project

Earlier task module for ფოლადის სახლი: stages, accept / review buttons, deadline extension requests, reason wizards, deadline reminders.
**Not installed on the live server** (version 19.0.1.0.1, last changed 2026-11-12). The installed task module is `steelhouse_task_flow`.

## Dependencies
`project`.

## Contents
- Models: `steelhouse.task.extension.request`, wizards `steelhouse.task.extension.wizard`, `steelhouse.task.reason.wizard`; extends `project.task`.
- Scheduled job: `ir_cron_deadline_notifications`.
- Data: `data/project_data.xml`.

## Install
Not to be installed next to `steelhouse_task_flow` without a check: both extend `project.task` with the same kind of rules.

## Open question
Keep in the repo or remove - see `../../Docs/PLAN.md`, Milestone 1.

## Docs
`../../README.md`, section „მოდული `steelhouse_project`“.
