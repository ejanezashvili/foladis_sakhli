<!-- last-synced: 2026-11-25, commit: c56cf43 -->
# Decisions

Entries D-1 … D-5 are inferred from the code and `README.md` / `Docs/გეგმა.md`; where the reasoning was not written down at the time it says "not recorded" instead of a guess.

### D-1: Built-in first, then OCA, then custom code
- Date: 2026-11-02 (first commit; `README.md`, `Docs/გეგმა.md`)
- Context: task management for 50–100 users on an existing Odoo 19.0 Community server.
- Decision: use Odoo's own features first, an OCA module second (`auditlog`, `web_responsive`), custom code last.
- Alternatives rejected: a separate system; Odoo Enterprise / Studio - not recorded why.
- Consequences: the requirements map in `Docs/გეგმა.md` marks every requirement N / C / O / X.

### D-2: A stage has a fixed meaning (`sh_kind`)
- Date: 2026-11-05 (first commit of `models/project_task_type.py`)
- Context: stages are per project in Odoo and carry no meaning; the flow (accept, review, return, hold, cancel) must be the same in every department.
- Decision: `project.task.type.sh_kind` (new, accepted, in_progress, on_hold, review, returned, done, cancelled); state follows the stage; reasons are asked in a wizard; only the reviewer or an administrator finishes, returns, cancels.
- Alternatives rejected: not recorded.
- Consequences: every rule in the module reads `sh_kind`, never a stage name or id.

### D-3: Sequences are built on Odoo's task dependencies
- Date: 2026-11-12 (first commit of `models/task_chain.py`)
- Context: a job goes through several departments one after another; some steps run at the same time.
- Decision: use the standard `depend_on_ids` / `dependent_ids`; add the step diagram, the stage lock, the "same step" link `sh_parallel_ids`, and treat the last task as the main task (never waiting, closed only after its steps).
- Alternatives rejected: a new "step" model - not recorded why; sub-tasks are kept for a different purpose (parts of one task).
- Consequences: standard dependency screens still work; steps are hidden from boards by `web_search_read` / `web_read_group` overrides.

### D-4: Visibility by a list, confidentiality removed
- Date: 2026-11-24 (19.0.1.176.0, commit `b274364`)
- Context: the client sent a list of who must see whose tasks (Excel, 2026-11-24); being in a department must no longer show its tasks.
- Decision: global record rules + stored `sh_party_user_ids` (the whole job to its participants) + `res.users.sh_see_*` set on "პროექტი → კონფიგურაცია → დავალებების ხილვა"; the confidential flag, role and board were deleted; "დამატებით ხედავენ" stays per task.
- Alternatives rejected: keeping the confidential role and board (teammates' 159–166). Standard project privacy / followers - **not recorded whether it was checked** (PLAN, Milestone 0).
- Consequences: a department head no longer sees the department's tasks automatically; 314 of 570 tasks that were confidential became visible by the normal rules.

### D-5: Several equal heads of a department
- Date: 2026-11-04 (first commit of `steelhouse_hr/models/hr_department.py`)
- Context: units in the company chart have more than one head with equal rights.
- Decision: `hr.department.manager_ids`; time off is approved first by the head(s) of the unit right under the company, then by the company heads; deputies take over approvals while a head is away.
- Alternatives rejected: the single standard `manager_id` - does not hold several people.
- Consequences: `sh_all_manager_user_ids` is used by the task write rule and by escalation.

### D-6: "დაწყების მოთხოვნა" only notifies; permission stays tied to a held step
- Date: 2026-11-25 (19.0.1.177.0–178.0, commits `d1d3e8d`, `c56cf43`)
- Context: the owner asked how a waiting step can ask to start, and how the previous one can open it. The system had only "▶ შემდეგის დაშვება", shown when the previous step is on hold.
- Decision: a button on the waiting step (form and card) that sends a notification to the people of every open previous task; at most once an hour; not on a main task. The rule itself is unchanged. Confirmed by the owner ("გააკეთე"; later "მთავარია რეალური იყოს" - no further additions).
- Alternatives rejected: letting the previous step's people allow the next one without putting their task on hold; buttons inside the sequence tab and the main task's card list - both offered, not taken.
- Consequences: when the previous step is "in progress", its people must put it on hold before they can allow the next one, or the author moves the step. Standard alternative (activity / @mention) - **not recorded as checked** (PLAN, Milestone 0).

### D-7: One live server, no local or staging instance
- Date: 2026-11-25 (owner's answer)
- Context: three people deploy to the same server; there is no second environment, and the server has one database without dbfilter.
- Decision: changes are checked on the live server, in the demo department with demo users; never a second database on the server. Every upgrade: database dump first, old module files kept, files put back when the upgrade log is not clean.
- Alternatives rejected: a local or staging Odoo - not planned at this stage.
- Consequences: a faulty change is seen by real users until fixed (19.0.1.177.0 showed the request button on main tasks; fixed in 178.0 the same day).

### D-8: No automated tests at this stage
- Date: 2026-11-25 (owner's answer)
- Context: no `tests/` in any module.
- Decision: not planned now. The recording scripts in `deploy/manual_video/` double as scripted checks of the main flows.
- Alternatives rejected: Odoo `TransactionCase` tests - would need an instance to run them on (D-7).
- Consequences: rules outside the recorded flows (visibility, reports, time off) are checked by hand only.

### D-9: Video manuals recorded from scripts on the live system
- Date: 2026-11-24 (owner chose the topics and "create test data, then delete")
- Context: users need manuals that show the real screens; the screens change with almost every version.
- Decision: playwright scripts drive the live UI as three demo users in a demo department; captions and a role chip are drawn into the page; ffmpeg writes mp4 (10–12 MB each).
- Alternatives rejected: recording by hand - has to be redone by hand after every change.
- Consequences: the demo department and users stay on the live server until `cleanup_demo.py` is run; the mp4 files are not in git.
