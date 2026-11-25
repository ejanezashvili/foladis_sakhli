<!-- last-synced: 2026-11-25, commit: c56cf43 -->
# Plan — remaining work

Done work and its history: `Docs/გეგმა.md` (stages, `## Status`) and `README.md` (version by version). This file lists only what is left.
Nothing below starts before the owner approves this file.

## Milestone 0 — Standard-first verification
One step per requirement whose reason for custom code was not recorded. Check the standard feature on the live server, write the result into `Docs/SPEC.md` (Standard-first check) and a `D-<n>` entry in `Docs/DECISIONS.md`.

- [ ] Task visibility: can project privacy + followers + group record rules give "sees only the jobs he takes part in, plus the people / departments on a list"? (now: `security/project_rules.xml`, `models/task_visibility.py`)
- [ ] Start request: would a `mail.activity` on the previous task or an @mention be enough? (now: `models/task_start_request.py`)
- [ ] Repeating tasks: what in standard recurring tasks did not fit? (now: `models/task_repeat.py`)
- [ ] Time off per quarter: what in accrual plans did not fit? (now: `steelhouse_hr/models/leave_balance.py`, `cron_quarter_allocations`)
- [ ] Overdue notifications, weekly digest, monthly mandatory days: standard automated actions / digests checked? (now: `models/task_overdue.py`, `task_notify.py`, `steelhouse_hr/models/mandatory_day_monthly.py`)

## Milestone 1 — Open items (risky / unknown first)
- [ ] HTTPS on the server (now plain HTTP) - server config, outside the repo.
- [ ] SMTP for outgoing mail; then requirement 4.7 (e-mail notifications) - `Docs/გეგმა.md`.
- [ ] Decide on `addons/steelhouse_project` (not installed): remove from the repo or mark as archived - `addons/steelhouse_project/`, `README.md`.
- [ ] Close or remove the stale `[ ]` items about confidential tasks in `Docs/გეგმა.md` (confidentiality was removed in 19.0.1.176.0) and rewrite row 8.2–8.3 of its requirements map.
- [ ] Remaining `[ ]` items of `Docs/გეგმა.md` ("პროექტების ტესტი" and the points under it) - go through with the owner.

## Milestone 3 — HR processes as tasks („კადრები“) — approved 2026-11-25 („დაიწყე“), module installed (19.0.1.3.0)
Source: the client's three documents (2026-11-25, `Docs/HR/` - not in git): vacancy, hiring, dismissal. Option „დ“
chosen by the owner (2026-11-25); the people are chosen in settings, not fixed in code. D-10.
New module `addons/steelhouse_hr_tasks` (depends on `steelhouse_task_flow`, `hr`); `steelhouse_task_flow` files are
not edited - no version / file clashes with the teammates.
- [x] Settings „კადრები → პარამეტრები“: HR manager(s), director (approves), time keeping (მარიამ პაპაშვილი),
      internal security; legal entities (`steelhouse.legal.entity`: name, organisation code, accountant(s),
      lawyer(s)) - `models/hr_task_config.py`, `views/hr_task_config_views.xml`, access rows.
- [x] Board „კადრები“ (one project) - changed while building: the shared columns stay, the process has its own status field `sh_hr_state` (own columns would show in every board's merged views). Original idea: own columns, each tied to an existing stage kind so the
      reports / home page / calendar keep counting right: ახალი (new) → დირექტორთან (review) → დამტკიცებულია
      (in_progress) → გადახდაში (in_progress, vacancy only) → დასრულებულია (done); უარყოფილია / გაუქმებულია
      (cancelled, with the reason window of `task_flow`) - `data/hr_task_board.xml`.
- [x] Task fields by kind (`sh_hr_kind`: ვაკანსია / აყვანა / გათავისუფლება) - vacancy: position, duties,
      requirements, place, schedule, salary; hiring: ID number, phone, address, bank account, e-mail, position,
      salary, schedule, start date, legal entity (+ its code); dismissal: scanned application (attachment),
      real reason, special conditions, last working day, company property handed over - `models/task_hr_process.py`.
- [x] Rule: a task leaves „ახალი“ only with every required field of its kind filled (list of the missing ones).
- [x] Buttons: HR manager „დირექტორს გაგზავნა“; director only „დამტკიცება“ / „უარყოფა“ (reason). On approval:
      hiring / dismissal - the legal entity's accountant + lawyer are added, sub-tasks are made (lawyer:
      documents; time keeping: registration (hiring); accountant: RS.ge; security (dismissal, when ticked)).
- [x] Menu „კადრები“: new vacancy / hiring / dismissal (each opens the form with its kind), the board.
- [x] Visibility: only the people of the job (teammates' `sh_party_user_ids`, 19.0.1.176.0) - check that the
      HR manager, the director, the invited accountant and lawyer see it, other employees do not.
- [ ] Check on the live server with test people, then the owner; `README.md`, `addons/steelhouse_hr_tasks/README.md`.

## Milestone 2 — Housekeeping
- [ ] Remove the demo department and the users `demo.manager` / `demo.employee` / `demo.employee2` from the live server when no more recordings are needed - `deploy/manual_video/cleanup_demo.py` (dry run first).
- [ ] Commit the pending changes: `README.md`, `Docs/გეგმა.md`, `deploy/manual_video/v4_sequence.py`, the new docs.
- [ ] Decide where the video manuals live (44 MB of mp4; not in git now) - `Docs/ვიდეო მანუალები/`.
- [ ] Remove `deploy/manual_video/t_dom.py` (exploration script).

## Not planned at this stage
- Automated tests (D-8).
- A local or staging Odoo instance (D-7).
- Permission to start the next step when the previous one is not on hold (D-6).

## Status
Not started (this list). Earlier stages: done, see `Docs/გეგმა.md`.
