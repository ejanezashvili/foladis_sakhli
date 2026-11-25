<!-- last-synced: 2026-11-25, commit: c56cf43 -->
# Technical spec — ფოლადის სახლი (Odoo 19.0 Community)

Modules: `steelhouse_task_flow` 19.0.1.178.0 (installed), `steelhouse_hr` 19.0.1.64.0 (installed), `steelhouse_project` 19.0.1.0.1 (not installed).
Version-by-version detail: `README.md`. The field and view tables below are generated from the sources (commit in line 1).

## Data model

### Module `steelhouse_task_flow`


**`hr.department`** - MODIFIED - `models/hr_department.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_all_manager_user_ids` | Many2many |  | compute `_compute_sh_all_manager_user_ids` | -> `res.users`, stored |


**`project.project`** - MODIFIED - `models/project_project.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_is_department` | Boolean |  |  |  |
| `sh_department_id` | Many2one |  |  | -> `hr.department` |
| `sh_task_ids` | One2many |  |  | -> `project.task` |
| `sh_overdue_count` | Integer |  | compute `_compute_sh_overdue_count` |  |


**`project.task`** - MODIFIED - `models/project_task.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `partner_id` | Many2one |  |  |  |
| `sh_project_id` | Many2one |  |  | -> `project.project`, tracked |
| `sh_department_id` | Many2one |  | related `project_id.sh_department_id` | stored |
| `sh_kind` | Selection |  | related `stage_id.sh_kind` | stored |
| `reviewer_ids` | Many2many |  |  | -> `res.users`, tracked |
| `reviewer_id` | Many2one |  | compute `_compute_reviewer_id` | -> `res.users`, stored |
| `evidence_required` | Boolean |  |  | tracked |
| `hold_reason` | Text |  |  | tracked, not copied |
| `hold_date` | Date |  |  | tracked, not copied |
| `sh_hold_info` | Char |  | compute `_compute_sh_hold_info` |  |
| `resume_date` | Date |  |  | tracked, not copied |
| `return_reason` | Text |  |  | tracked, not copied |
| `cancel_reason` | Text |  |  | tracked, not copied |
| `priority` | Selection |  |  |  |
| `sh_responsible_id` | Many2one |  |  | -> `res.users`, tracked |
| `sh_work_start` | Date |  |  | tracked |
| `sh_category` | Selection |  |  | tracked |
| `sh_branch` | Selection |  |  | tracked |
| `sh_manual_progress` | Integer |  |  |  |
| `sh_progress` | Integer |  | compute `_compute_sh_progress` | stored |


**`project.task.type`** - MODIFIED - `models/project_task_type.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_kind` | Selection |  |  |  |

- `project.task` - MODIFIED - `models/task_approvals.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_card.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_comment_count` | Integer |  | compute `_compute_sh_comment_count` |  |
| `sh_deadline_str` | Char |  | compute `_compute_sh_deadline_str` |  |


**`project.task`** - MODIFIED - `models/task_card_lists.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_is_step` | Boolean |  | compute `_compute_sh_is_step` | stored |
| `sh_step_total` | Integer |  | compute `_compute_sh_step_counts` |  |
| `sh_step_done` | Integer |  | compute `_compute_sh_step_counts` |  |
| `sh_step_badge` | Selection |  | compute `_compute_sh_step_badge` |  |
| `sh_step_pos` | Char |  | compute `_compute_sh_step_badge` |  |
| `sh_step_info` | Text |  | compute `_compute_sh_step_badge` |  |


**`project.task`** - MODIFIED - `models/task_card_step.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_step_main_label` | Char |  | compute `_compute_sh_step_chain` |  |
| `sh_step_chain_total` | Integer |  | compute `_compute_sh_step_chain` |  |
| `sh_step_chain_done` | Integer |  | compute `_compute_sh_step_chain` |  |


**`project.task`** - MODIFIED - `models/task_chain.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_chain` | Char |  | compute `_compute_sh_chain` |  |
| `sh_parallel_ids` | Many2many |  |  | -> `project.task`, not copied |
| `sh_waiting_for` | Char |  | compute `_compute_sh_waiting_for` |  |

- `project.task` - MODIFIED - `models/task_chain_check.py`: no fields (methods only)
- `project.task` - MODIFIED - `models/task_chain_main.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_chat.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_channel_id` | Many2one |  |  | -> `discuss.channel`, not copied |

- `project.task` - MODIFIED - `models/task_company_week.py`: no fields (methods only)
- `project.task` - MODIFIED - `models/task_dashboard.py`: no fields (methods only)
- `project.task` - MODIFIED - `models/task_edit_lock.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_final.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_final_note` | Text |  |  | tracked, not copied |
| `sh_final_attachment_ids` | Many2many |  |  | -> `ir.attachment`, not copied |
| `sh_done_user_id` | Many2one |  |  | -> `res.users`, not copied |
| `sh_done_date` | Datetime |  |  | not copied |
| `sh_is_admin` | Boolean |  | compute `_compute_sh_is_admin` |  |


**`steelhouse.task.final.wizard`** - NEW (wizard) - `models/task_final.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `note` | Text |  |  |  |
| `attachment_ids` | Many2many |  |  | -> `ir.attachment` |


**`project.task`** - MODIFIED - `models/task_hold.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_held_by_project` | Boolean |  |  | not copied |
| `sh_continue_ok` | Boolean |  |  | not copied |
| `sh_prev_held` | Boolean |  | compute `_compute_sh_prev_held` |  |
| `sh_prev_held_info` | Char |  | compute `_compute_sh_prev_held` |  |
| `sh_can_continue` | Boolean |  | compute `_compute_sh_can_continue` |  |
| `sh_can_allow_next` | Boolean |  | compute `_compute_sh_can_allow_next` |  |
| `sh_allow_next_info` | Char |  | compute `_compute_sh_can_allow_next` |  |


**`project.project`** - MODIFIED - `models/task_hold.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_on_hold` | Boolean |  |  | tracked, not copied |
| `sh_hold_reason` | Text |  |  | not copied |
| `sh_hold_date` | Date |  |  | not copied |
| `sh_resume_date` | Date |  |  | not copied |
| `sh_can_hold` | Boolean |  | compute `_compute_sh_can_hold` |  |


**`steelhouse.project.hold.wizard`** - NEW (wizard) - `models/task_hold.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `project_id` | Many2one | yes |  | -> `project.project` |
| `reason` | Text | yes |  |  |
| `resume_date` | Date |  |  |  |

- `project.task` - MODIFIED - `models/task_log.py`: no fields (methods only)
- `ir.attachment` - MODIFIED - `models/task_log.py`: no fields (methods only)

**`res.users`** - MODIFIED - `models/task_notify.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `notification_type` | Selection |  |  |  |


**`project.task`** - MODIFIED - `models/task_notify.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_escalated` | Boolean |  |  | not copied |


**`project.project`** - MODIFIED - `models/task_number.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_code` | Char |  |  |  |
| `sh_number_next` | Integer |  |  | not copied |


**`project.task`** - MODIFIED - `models/task_number.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_number` | Char |  |  | not copied |


**`project.task`** - MODIFIED - `models/task_overdue.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_is_overdue` | Boolean |  | compute `_compute_sh_is_overdue` |  |
| `sh_overdue_notified` | Boolean |  |  | not copied |

- `project.task` - MODIFIED - `models/task_pdf.py`: no fields (methods only)
- `report.steelhouse_task_flow.report_sh_table` - NEW (abstract) - `models/task_pdf.py`: no fields (methods only)
- `project.task` - MODIFIED - `models/task_personal.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_phase.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_phase` | Selection |  | compute `_compute_sh_phase` | stored |


**`project.task`** - MODIFIED - `models/task_repeat.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_repeat` | Boolean |  |  | tracked, not copied |
| `sh_repeat_interval` | Integer |  |  | not copied |
| `sh_repeat_unit` | Selection |  |  | not copied |
| `sh_repeat_start` | Date |  |  | tracked, not copied |
| `sh_repeat_next` | Date |  |  | not copied |
| `sh_repeat_until_type` | Selection |  |  | not copied |
| `sh_repeat_until` | Date |  |  | not copied |
| `sh_create_date_str` | Char |  | compute `_compute_sh_create_date_str` |  |
| `sh_create_datetime_str` | Char |  | compute `_compute_sh_create_date_str` |  |
| `sh_repeat_origin_id` | Many2one |  |  | -> `project.task`, not copied |

- `project.task` - MODIFIED - `models/task_reports.py`: no fields (methods only)

**`sh.task.flow.event`** - NEW - `models/task_returns.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `kind` | Selection | yes |  |  |
| `date` | Datetime | yes |  |  |
| `user_id` | Many2one |  |  | -> `res.users` |
| `reason` | Text |  |  |  |


**`project.task`** - MODIFIED - `models/task_returns.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_return_count` | Integer |  | compute `_compute_sh_returns` |  |
| `sh_return_note` | Char |  | compute `_compute_sh_returns` |  |


**`project.task`** - MODIFIED - `models/task_stagebar.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_can_close` | Boolean |  | compute `_compute_sh_can_close` |  |


**`project.task`** - MODIFIED - `models/task_start_request.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_start_request_date` | Datetime |  |  | not copied |
| `sh_can_request_start` | Boolean |  | compute `_compute_sh_can_request_start` |  |


**`steelhouse.task.section`** - NEW - `models/task_steps.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `name` | Char |  |  |  |
| `sequence` | Integer |  |  |  |
| `user_id` | Many2one |  |  | -> `res.users` |
| `date_deadline` | Date |  |  |  |
| `done_date` | Datetime |  |  |  |
| `subtask_ids` | One2many |  |  | -> `project.task` |


**`project.task`** - MODIFIED - `models/task_steps.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_section_id` | Many2one |  |  | -> `steelhouse.task.section`, not copied |
| `sh_section_ids` | One2many |  |  | -> `steelhouse.task.section` |
| `sh_steps` | Char |  | compute `_compute_sh_steps` |  |


**`project.task`** - MODIFIED - `models/task_template.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_template_count` | Integer |  | compute `_compute_sh_template_count` |  |


**`steelhouse.task.template.wizard`** - NEW (wizard) - `models/task_template.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `name` | Char | yes |  |  |

- `project.task` - MODIFIED - `models/task_timeline.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_view_departments.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_department_project_ids` | Many2many |  |  | -> `project.project`, tracked |
| `sh_view_department_ids` | Many2many |  | compute `_compute_sh_view_department_ids` | -> `hr.department`, stored |
| `sh_is_mine` | Boolean |  | compute `_compute_sh_is_mine` |  |


**`res.users`** - MODIFIED - `models/task_visibility.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_see_all_tasks` | Boolean |  |  |  |
| `sh_see_subordinates` | Boolean |  |  |  |
| `sh_see_department_ids` | Many2many |  |  | -> `hr.department` |
| `sh_see_user_ids` | Many2many |  |  | -> `res.users` |
| `sh_see_user_all_ids` | Many2many |  | compute `_compute_sh_see_all_ids` | -> `res.users` |
| `sh_see_department_all_ids` | Many2many |  | compute `_compute_sh_see_all_ids` | -> `hr.department` |

- `hr.employee` - MODIFIED - `models/task_visibility.py`: no fields (methods only)
- `hr.department` - MODIFIED - `models/task_visibility.py`: no fields (methods only)

**`project.task`** - MODIFIED - `models/task_visibility.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_party_user_ids` | Many2many |  |  | -> `res.users`, not copied |
| `sh_extra_viewer_ids` | Many2many |  |  | -> `res.users`, tracked |
| `sh_job_viewer_ids` | Many2many |  |  | -> `res.users`, not copied |


**`project.task`** - MODIFIED - `models/task_worktime.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_wt_first` | Datetime |  |  | not copied |
| `sh_wt_run_from` | Datetime |  |  | not copied |
| `sh_wt_secs` | Float |  |  | not copied |
| `sh_wt_end` | Datetime |  |  | not copied |
| `sh_work_time` | Char |  | compute `_compute_sh_work_time` |  |
| `sh_work_time_note` | Char |  | compute `_compute_sh_work_time` |  |
| `sh_work_running` | Boolean |  | compute `_compute_sh_work_time` |  |


**`steelhouse.task.flow.wizard`** - NEW (wizard) - `wizard/task_flow_wizard.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `mode` | Selection | yes |  |  |
| `reason` | Text | yes |  |  |
| `resume_date` | Date |  |  |  |
| `hold_date` | Date |  |  |  |


### Module `steelhouse_hr`


**`mail.activity.type`** - MODIFIED - `models/activity_type.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_system_only` | Boolean |  |  |  |


**`mail.activity`** - MODIFIED - `models/activity_type.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `activity_type_id` | Many2one |  |  |  |


**`mail.activity.schedule`** - MODIFIED (wizard) - `models/activity_type.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `activity_type_id` | Many2one |  |  |  |

- `mail.activity` - MODIFIED - `models/activity_type.py`: no fields (methods only)
- `res.users` - MODIFIED - `models/activity_type.py`: no fields (methods only)

**`hr.employee`** - MODIFIED - `models/employee_absence.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_absence_info` | Char |  | compute `_compute_sh_absence_info` |  |


**`hr.employee.public`** - MODIFIED - `models/employee_absence.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_absence_info` | Char |  | compute `_compute_sh_absence_info` |  |


**`hr.department`** - MODIFIED - `models/hr_department.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `deputy_id` | Many2one |  |  | -> `hr.employee`, tracked |
| `manager_ids` | Many2many |  |  | -> `hr.employee` |
| `sh_head_title` | Char |  |  |  |
| `sh_heads_html` | Html |  | compute `_compute_sh_heads_html` |  |
| `sh_headcount` | Integer |  | compute `_compute_sh_headcount` |  |

- `hr.job` - MODIFIED - `models/hr_department.py`: no fields (methods only)

**`hr.employee`** - MODIFIED - `models/hr_employee.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_manager_ids` | Many2many |  | compute `_compute_sh_manager_ids` | -> `hr.employee` |
| `sh_co_manager_ids` | Many2many |  | compute `_compute_sh_manager_ids` | -> `hr.employee` |
| `sh_my_team` | Boolean |  | compute `_compute_sh_my_team` |  |
| `sh_head_user_ids` | Many2many |  | compute `_compute_sh_head_user_ids` | -> `res.users` |
| `sh_under_me` | Boolean |  | compute `_compute_sh_under_me` |  |
| `sh_extra_job_ids` | Many2many |  |  | -> `hr.job` |


**`hr.employee.public`** - MODIFIED - `models/hr_employee.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_manager_ids` | Many2many |  | compute `_compute_sh_manager_ids` | -> `hr.employee.public` |
| `sh_co_manager_ids` | Many2many |  | compute `_compute_sh_manager_ids` | -> `hr.employee.public` |
| `sh_my_team` | Boolean |  | compute `_compute_sh_my_team` |  |


**`steelhouse.leave.delegation`** - NEW - `models/hr_leave.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `leave_id` | Many2one | yes |  | -> `hr.leave` |
| `employee_id` | Many2one |  | related `leave_id.employee_id` | stored |
| `department_id` | Many2one | yes |  | -> `hr.department` |
| `deputy_id` | Many2one |  |  | -> `hr.employee` |
| `deputy_department_id` | Many2one |  | related `deputy_id.department_id` |  |


**`hr.leave`** - MODIFIED - `models/hr_leave.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_head_approved_user_ids` | Many2many |  |  | -> `res.users`, not copied |
| `delegation_ids` | One2many |  |  | -> `steelhouse.leave.delegation`, not copied |

- `hr.leave.type` - MODIFIED - `models/hr_leave.py`: no fields (methods only)

**`res.company`** - MODIFIED - `models/leave_approval_flow.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_hr_user_id` | Many2one |  |  | -> `res.users` |


**`hr.leave`** - MODIFIED - `models/leave_approval_flow.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_no_head` | Boolean |  | compute `_compute_sh_no_head` |  |
| `sh_approval_path` | Char |  | compute `_compute_sh_approval_path` |  |

- `hr.leave.allocation` - MODIFIED - `models/leave_approval_flow.py`: no fields (methods only)

**`steelhouse.leave.balance`** - NEW - `models/leave_balance.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `employee_id` | Many2one |  |  | -> `hr.employee` |
| `user_id` | Many2one |  |  | -> `res.users` |
| `department_id` | Many2one |  |  | -> `hr.department` |
| `leave_type_id` | Many2one |  |  | -> `hr.leave.type` |
| `sequence` | Integer |  |  |  |
| `requires_allocation` | Boolean |  |  |  |
| `period_from` | Date |  |  |  |
| `period_to` | Date |  |  |  |
| `status` | Selection |  |  |  |
| `allocated` | Float |  |  |  |
| `used` | Float |  |  |  |
| `pending` | Float |  |  |  |
| `remaining` | Float |  |  |  |
| `burned` | Float |  |  |  |


**`hr.leave.type`** - MODIFIED - `models/leave_report.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_report_kind` | Selection |  |  |  |

- `sh.leave.report` - NEW (abstract) - `models/leave_report.py`: no fields (methods only)
- `report.steelhouse_hr.report_sh_leave` - NEW (abstract) - `models/leave_report.py`: no fields (methods only)

**`hr.leave.type`** - MODIFIED - `models/leave_rules.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_calendar_days` | Boolean |  |  |  |
| `sh_ignore_mandatory_days` | Boolean |  |  |  |
| `sh_quarter_days` | Float |  |  |  |


**`hr.employee`** - MODIFIED - `models/leave_rules.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_quarter_start` | Date |  |  |  |
| `sh_quarter_next_day` | Boolean |  |  |  |


**`hr.leave.allocation`** - MODIFIED - `models/leave_rules.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_quarter_start` | Date |  |  | not copied |

- `hr.leave` - MODIFIED - `models/leave_rules.py`: no fields (methods only)

**`hr.leave.mandatory.day`** - MODIFIED - `models/mandatory_day_monthly.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_repeat_monthly` | Boolean |  |  |  |
| `sh_template_id` | Many2one |  |  | -> `hr.leave.mandatory.day` |


**`res.users`** - MODIFIED - `models/notification_channel.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `sh_notify_email_too` | Boolean |  |  |  |
| `sh_notification_channel` | Selection |  | compute `_compute_sh_notification_channel` |  |

- `mail.thread` - MODIFIED (abstract) - `models/notification_channel.py`: no fields (methods only)
- `mail.notification` - MODIFIED - `models/notification_channel.py`: no fields (methods only)

### Module `steelhouse_project`


**`project.task`** - MODIFIED - `models/project_task.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `responsible_id` | Many2one |  |  | -> `res.users`, tracked |
| `reviewer_id` | Many2one |  |  | -> `res.users`, tracked, not copied |
| `sh_stage_key` | Selection |  | compute `_compute_sh_stage_key` | stored |
| `date_deadline_original` | Datetime |  |  | not copied |
| `deadline_extension_count` | Integer |  |  | not copied |
| `extension_request_ids` | One2many |  |  | -> `steelhouse.task.extension.request`, not copied |
| `has_pending_extension` | Boolean |  | compute `_compute_has_pending_extension` | stored |
| `deadline_reminder_sent` | Boolean |  |  | not copied |
| `overdue_notified` | Boolean |  |  | not copied |
| `evidence_required` | Boolean |  |  |  |
| `hold_reason` | Text |  |  | tracked, not copied |
| `resume_date` | Date |  |  | tracked, not copied |
| `last_return_reason` | Text |  |  | tracked, not copied |
| `return_count` | Integer |  |  | not copied |
| `cancel_reason` | Text |  |  | tracked, not copied |
| `date_done` | Datetime |  |  | not copied |
| `done_on_time` | Boolean |  | compute `_compute_done_on_time` | stored |
| `done_within_original` | Boolean |  | compute `_compute_done_on_time` | stored |


**`steelhouse.task.extension.request`** - NEW - `models/task_extension_request.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `requested_by_id` | Many2one | yes |  | -> `res.users` |
| `old_deadline` | Datetime |  |  |  |
| `new_deadline` | Datetime | yes |  |  |
| `reason` | Text | yes |  |  |
| `state` | Selection | yes |  |  |
| `decided_by_id` | Many2one |  |  | -> `res.users` |
| `decision_date` | Datetime |  |  |  |


**`steelhouse.task.extension.wizard`** - NEW (wizard) - `wizard/task_extension_wizard.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_id` | Many2one | yes |  | -> `project.task` |
| `current_deadline` | Datetime |  | related `task_id.date_deadline` |  |
| `new_deadline` | Datetime | yes |  |  |
| `reason` | Text | yes |  |  |


**`steelhouse.task.reason.wizard`** - NEW (wizard) - `wizard/task_reason_wizard.py`

| field | type | required | compute/related | notes |
|---|---|---|---|---|
| `task_ids` | Many2many | yes |  | -> `project.task` |
| `mode` | Selection | yes |  |  |
| `reason` | Text | yes |  |  |
| `resume_date` | Date |  |  |  |

## Business logic

| # | Rule | Trigger | Condition | Action | AC | Standard coverage |
|---|---|---|---|---|---|---|
| B-1 | Stage kind drives the state | `project.task.write(stage_id)` | stage has `sh_kind` | state follows the stage and back (`models/project_task.py`) | AC-2, AC-3 | custom: standard stages carry no meaning (D-2) |
| B-2 | Accept | button `action_sh_accept` | user in `user_ids`, kind `new`, not waiting | stage -> `accepted` | AC-2 | custom (D-2) |
| B-3 | Mark done | button `action_sh_mark_done` | user in `user_ids`, kind `accepted` / `in_progress` / `returned` | stage -> `review`; evidence required when the task asks for it | AC-3 | custom (D-2) |
| B-4 | Review | `action_sh_review_ok`, `sh_approval_approve`, `sh_approval_reject(reason)` | user in `reviewer_ids` or project administrator | `done` (with the final wizard) or `returned` with a reason | AC-3, AC-4, AC-5 | custom (D-2) |
| B-5 | Reasons | stage change to `on_hold` / `returned` / `cancelled` | - | wizard `steelhouse.task.flow.wizard`, reason required | AC-4 | custom (D-2) |
| B-6 | Sequence lock | `write(stage_id)` to `accepted` / `in_progress` / `review` / `done` | task has an open previous task (`depend_on_ids`) | `UserError` listing the previous tasks (`models/task_chain.py`) | AC-7 | standard: task dependencies (`depend_on_ids`), partial - standard does not block the stage (D-3) |
| B-7 | Main task | - | task has previous tasks and no next task (`_sh_is_main`) | never "waiting"; cannot go to `review` while a step or sub-task is open (`models/task_chain_main.py`, `task_chain_check.py`) | AC-6 | custom (D-3) |
| B-8 | Same step | `sh_chain_create(parallel_ids)`, `sh_chain_move(mode='into')` | - | tasks linked by `sh_parallel_ids` share previous and next tasks | AC-8 | custom (D-3) |
| B-9 | Move a step | `sh_chain_move(task_id, mode, target_level)` | user may write the task the tab is on | re-links `depend_on_ids`; an arrow over the place the step left is dropped when another path covers it (19.0.1.177.0) | AC-8 | custom (D-3) |
| B-10 | Hold and resume | stage leaves `on_hold` for a working stage | - | task always lands in `new` (`models/task_hold.py`) | AC-11 | custom (D-2) |
| B-11 | Let the next start | `action_sh_allow_next` / `action_sh_continue` | every open previous task of the next one is on hold; user is performer / main responsible / reviewer of the held task or project administrator | `sh_continue_ok = True` on the next task; note on both | AC-10 | custom (D-6) |
| B-12 | Start request | `action_sh_request_start` | task has an open previous task, is not a main task, user is its performer / main responsible, last request older than 1 h | message with notification to the people of every open previous task; `sh_start_request_date` set (`models/task_start_request.py`) | AC-12 | custom - standard alternative not recorded (see Standard-first check) |
| B-13 | Who sees a task | global rule `rule_sh_task_department` | not project administrator, not `sh_see_all_tasks` | own jobs (`sh_party_user_ids`), created, `sh_job_viewer_ids`, people and departments given on "დავალებების ხილვა" | AC-13 | custom - standard alternative not recorded (D-4) |
| B-14 | Who changes a task | global rule `rule_sh_task_department_write` | not project administrator | performer, main responsible, reviewer, creator, head of the task's department | AC-14 | custom (D-4) |
| B-15 | Steps off the boards | `web_search_read` / `web_read_group` on `project.task` | no explicit ids in the domain | steps (`sh_is_step`) hidden; a performer still sees his own (`models/task_card_lists.py`) | AC-1, AC-9 | custom (D-3) |
| B-16 | Repeat on a date | cron `ir_cron_sh_repeat` (hourly) | task marked repeating | next task created (`models/task_repeat.py`) | - | standard: recurring tasks - reason for custom not recorded |
| B-17 | Overdue and escalation | cron `ir_cron_sh_overdue_notify` (hourly) | deadline passed | notifications (`models/task_overdue.py`, `task_notify.py`) | - | not recorded |
| B-18 | Weekly digest | cron `ir_cron_sh_weekly_digest` (daily) | - | summary message per user (`models/task_notify.py`) | - | not recorded |
| B-19 | Personal columns | cron `ir_cron_sh_place_personal` (daily) | - | "ჩემი დავალებები" columns by creation date (`models/task_personal.py`) | AC-1 | standard: personal stages, partial |
| B-20 | Time off approval order | `hr.leave` approval (`models/leave_approval_flow.py`) | - | first approval by the head(s) of the unit right under the company, then the company heads | AC-16 | standard: time off validation by manager / officer, partial - several equal heads (D-5) |
| B-21 | Deputies | cron `cron_sync_leave_approvals` (hourly) | approver is on time off with a delegation | approval activities move to the deputy and back | AC-16 | custom (D-5) |
| B-22 | Quarter allocations | cron `cron_quarter_allocations` (daily) | - | time off days granted per quarter; balance kept per period (`steelhouse.leave.balance`) | - | standard: accrual plans - reason for custom not recorded |
| B-23 | Monthly mandatory days | cron `cron_mandatory_days_monthly` (daily) | - | `hr.leave.mandatory.day` generated every month | - | not recorded |

## Standard-first check

| Requirement | Standard feature checked | Covers it? | If no -> custom approach + DECISIONS ref |
|---|---|---|---|
| Stages with a fixed meaning, review by the author | project stages, task state | partial | `project.task.type.sh_kind` + buttons (D-2) |
| Tasks one after another, across departments | task dependencies (`depend_on_ids` / `dependent_ids`) | partial | built on the standard dependencies, widget and lock on top (D-3) |
| Who sees which task | project privacy, followers, record rules | not recorded | global record rules + `sh_party_user_ids` (D-4) - **justification not recorded** |
| Several equal heads of a department | `hr.department.manager_id` (one) | no | `manager_ids` (D-5) |
| Audit log | - | no | OCA `auditlog` (D-1) |
| Asking to start a waiting step | activities (`mail.activity`), @mention in the chatter | not recorded | `action_sh_request_start` (D-6) - **justification not recorded** |
| Repeating tasks | standard recurring tasks | not recorded | `models/task_repeat.py` - **justification not recorded** |
| Time off days per quarter | accrual plans | not recorded | `cron_quarter_allocations` - **justification not recorded** |

## Views / UI

Client actions (OWL): `action_sh_task_dashboard` ("მთავარი"), `action_sh_task_approvals` ("დადასტურებები"), `action_sh_task_timeline`, `action_sh_report_deadline`, `action_sh_report_stops`, `action_sh_leave_report`.
Field / view widgets: `sh_task_chain` (tab "თანმიმდევრობა"), `sh_card_lists` (list inside a kanban card), `steelhouse_department_hierarchy`, `steelhouse_employee_hierarchy`.
Menus: `menu_sh_task_dashboard`, `menu_sh_approvals_root`, `menu_sh_recurring_tasks`, `menu_sh_report_deadline`, `menu_sh_report_stops`, `menu_sh_task_timeline_report`, `menu_sh_task_visibility` (under `project.menu_project_config`), `menu_steelhouse_leave_balance_all`, `menu_sh_leave_report`.

### Module `steelhouse_task_flow`

| file | xml id | model | type | inherits | groups |
|---|---|---|---|---|---|
| `views/all_tasks_views.xml` | `view_sh_all_tasks_search` | `project.task` | search |  |  |
| `views/project_project_views.xml` | `view_sh_department_project_kanban` | `project.project` | extension | `project.view_project_kanban` |  |
| `views/project_project_views.xml` | `view_sh_project_search_overdue` | `project.project` | extension | `project.view_project_project_filter` |  |
| `views/project_project_views.xml` | `view_sh_department_project_list` | `project.project` | extension | `project.view_project` |  |
| `views/project_project_views.xml` | `view_sh_project_form` | `project.project` | extension | `project.edit_project` |  |
| `views/project_task_type_views.xml` | `task_type_edit_steelhouse` | `project.task.type` | extension | `project.task_type_edit` |  |
| `views/project_task_type_views.xml` | `task_type_tree_steelhouse` | `project.task.type` | extension | `project.task_type_tree` |  |
| `views/project_task_views.xml` | `view_task_form_steelhouse_flow` | `project.task` | extension | `project.view_task_form2` |  |
| `views/project_task_views.xml` | `view_task_kanban_steelhouse_flow` | `project.task` | extension | `project.view_task_kanban` |  |
| `views/project_task_views.xml` | `view_task_list_steelhouse_flow` | `project.task` | extension | `project.project_task_view_tree_main_base` |  |
| `views/project_task_views.xml` | `view_task_search_steelhouse_number` | `project.task` | extension | `project.view_task_search_form` |  |
| `views/special_boards_views.xml` | `view_sh_special_task_kanban` | `project.task` | extension | `project.view_task_kanban` |  |
| `views/task_card_step_views.xml` | `view_task_kanban_sh_card_step` | `project.task` | extension | `steelhouse_task_flow.view_task_kanban_steelhouse_flow` |  |
| `views/task_final_views.xml` | `view_sh_task_final_wizard_form` | `steelhouse.task.final.wizard` | form |  |  |
| `views/task_hold_views.xml` | `view_task_form_sh_hold` | `project.task` | extension | `steelhouse_task_flow.view_task_form_steelhouse_flow` |  |
| `views/task_hold_views.xml` | `view_task_kanban_sh_hold` | `project.task` | extension | `steelhouse_task_flow.view_task_kanban_steelhouse_flow` |  |
| `views/task_hold_views.xml` | `view_project_form_sh_hold` | `project.project` | extension | `project.edit_project` |  |
| `views/task_hold_views.xml` | `view_project_kanban_sh_hold` | `project.project` | extension | `project.view_project_kanban` |  |
| `views/task_hold_views.xml` | `view_sh_project_hold_wizard` | `steelhouse.project.hold.wizard` | form |  |  |
| `views/task_stagebar_views.xml` | `view_task_form_sh_stagebar` | `project.task` | extension | `project.view_task_form2` |  |
| `views/task_start_request_views.xml` | `view_task_form_sh_start_request` | `project.task` | extension | `steelhouse_task_flow.view_task_form_steelhouse_flow` |  |
| `views/task_start_request_views.xml` | `view_task_kanban_sh_start_request` | `project.task` | extension | `steelhouse_task_flow.view_task_kanban_steelhouse_flow` |  |
| `views/task_template_views.xml` | `view_sh_task_template_wizard_form` | `steelhouse.task.template.wizard` | form |  |  |
| `views/task_template_views.xml` | `view_sh_task_templates_list` | `project.task` | list |  |  |
| `views/task_visibility_views.xml` | `view_sh_task_visibility_list` | `res.users` | list |  |  |
| `views/task_visibility_views.xml` | `view_sh_task_visibility_search` | `res.users` | search |  |  |
| `wizard/task_flow_wizard_views.xml` | `view_task_flow_wizard_form` | `steelhouse.task.flow.wizard` | form |  |  |

### Module `steelhouse_hr`

| file | xml id | model | type | inherits | groups |
|---|---|---|---|---|---|
| `views/hr_department_hierarchy_views.xml` | `hr_department_hierarchy_view_steelhouse` | `hr.department` | extension | `hr_org_chart.hr_department_hierarchy_view` |  |
| `views/hr_department_views.xml` | `view_department_form_steelhouse` | `hr.department` | extension | `hr.view_department_form` |  |
| `views/hr_department_views.xml` | `view_department_tree_steelhouse` | `hr.department` | extension | `hr.view_department_tree` |  |
| `views/hr_department_views.xml` | `hr_department_view_kanban_steelhouse` | `hr.department` | extension | `hr.hr_department_view_kanban` |  |
| `views/hr_department_views.xml` | `view_department_filter_steelhouse` | `hr.department` | extension | `hr.view_department_filter` |  |
| `views/hr_department_views.xml` | `hr_work_location_tree_view_steelhouse` | `hr.work.location` | extension | `hr.hr_work_location_tree_view` |  |
| `views/hr_department_views.xml` | `hr_work_location_form_view_steelhouse` | `hr.work.location` | extension | `hr.hr_work_location_form_view` |  |
| `views/hr_department_views.xml` | `view_resource_calendar_tree_steelhouse` | `resource.calendar` | extension | `resource.view_resource_calendar_tree` |  |
| `views/hr_department_views.xml` | `resource_calendar_form_steelhouse` | `resource.calendar` | extension | `resource.resource_calendar_form` |  |
| `views/hr_department_views.xml` | `hr_departure_reason_view_list_steelhouse` | `hr.departure.reason` | extension | `hr.hr_departure_reason_view_list` |  |
| `views/hr_department_views.xml` | `view_hr_job_tree_steelhouse` | `hr.job` | extension | `hr.view_hr_job_tree` |  |
| `views/hr_department_views.xml` | `view_hr_job_form_steelhouse` | `hr.job` | extension | `hr.view_hr_job_form` |  |
| `views/hr_employee_hierarchy_views.xml` | `hr_employee_hierarchy_view_steelhouse` | `hr.employee` | extension | `hr_org_chart.hr_employee_hierarchy_view` |  |
| `views/hr_employee_hierarchy_views.xml` | `hr_employee_public_hierarchy_view_steelhouse` | `hr.employee.public` | extension | `hr_org_chart.hr_employee_public_hierarchy_view` |  |
| `views/hr_employee_views.xml` | `view_employee_form_steelhouse` | `hr.employee` | extension | `hr.view_employee_form` |  |
| `views/hr_employee_views.xml` | `view_employee_tree_steelhouse` | `hr.employee` | extension | `hr.view_employee_tree` |  |
| `views/hr_employee_views.xml` | `hr_employee_public_view_form_steelhouse` | `hr.employee.public` | extension | `hr.hr_employee_public_view_form` |  |
| `views/hr_employee_views.xml` | `hr_employee_public_view_tree_steelhouse` | `hr.employee.public` | extension | `hr.hr_employee_public_view_tree` |  |
| `views/hr_employee_views.xml` | `view_employee_filter_steelhouse` | `hr.employee` | extension | `hr.view_employee_filter` |  |
| `views/hr_employee_views.xml` | `hr_employee_public_view_search_steelhouse` | `hr.employee.public` | extension | `hr.hr_employee_public_view_search` |  |
| `views/hr_employee_views.xml` | `hr_kanban_view_employees_steelhouse` | `hr.employee` | extension | `hr.hr_kanban_view_employees` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_form_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_form` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_form_dashboard_new_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_form_dashboard_new_time_off` |  |
| `views/hr_leave_views.xml` | `hr_leave_report_calendar_view_search_steelhouse` | `hr.leave.report.calendar` | extension | `hr_holidays.hr_leave_report_calendar_view_search` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_search_steelhouse` | `hr.leave` | extension | `hr_holidays.view_hr_holidays_filter` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_tree_my_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_tree_my` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_kanban_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_kanban` |  |
| `views/hr_leave_views.xml` | `hr_leave_view_tree_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_tree` |  |
| `views/leave_balance_views.xml` | `steelhouse_leave_balance_list` | `steelhouse.leave.balance` | list |  |  |
| `views/leave_balance_views.xml` | `steelhouse_leave_balance_search` | `steelhouse.leave.balance` | search |  |  |
| `views/leave_balance_views.xml` | `hr_leave_allocation_view_form_steelhouse` | `hr.leave.allocation` | extension | `hr_holidays.hr_leave_allocation_view_form` |  |
| `views/leave_balance_views.xml` | `hr_leave_allocation_view_form_dashboard_steelhouse` | `hr.leave.allocation` | extension | `hr_holidays.hr_leave_allocation_view_form_dashboard` |  |
| `views/leave_balance_views.xml` | `hr_leave_allocation_generate_multi_wizard_view_form_steelhouse` | `hr.leave.allocation.generate.multi.wizard` | extension | `hr_holidays.hr_leave_allocation_generate_multi_wizard_view_form` |  |
| `views/leave_balance_views.xml` | `view_holiday_status_normal_tree_steelhouse` | `hr.leave.type` | extension | `hr_holidays.view_holiday_status_normal_tree` |  |
| `views/leave_balance_views.xml` | `edit_holiday_status_form_steelhouse` | `hr.leave.type` | extension | `hr_holidays.edit_holiday_status_form` |  |
| `views/leave_balance_views.xml` | `hr_leave_mandatory_day_view_list_steelhouse` | `hr.leave.mandatory.day` | extension | `hr_holidays.hr_leave_mandatory_day_view_list` |  |
| `views/leave_balance_views.xml` | `resource_calendar_leaves_tree_inherit_steelhouse` | `resource.calendar.leaves` | extension | `hr_holidays.resource_calendar_leaves_tree_inherit` |  |
| `views/leave_balance_views.xml` | `hr_accrual_level_view_form_steelhouse` | `hr.leave.accrual.level` | extension | `hr_holidays.hr_accrual_level_view_form` |  |
| `views/leave_balance_views.xml` | `hr_accrual_plan_view_tree_steelhouse` | `hr.leave.accrual.plan` | extension | `hr_holidays.hr_accrual_plan_view_tree` |  |
| `views/leave_balance_views.xml` | `hr_accrual_plan_view_form_steelhouse` | `hr.leave.accrual.plan` | extension | `hr_holidays.hr_accrual_plan_view_form` |  |
| `views/leave_balance_views.xml` | `hr_leave_view_kanban_days_steelhouse` | `hr.leave` | extension | `hr_holidays.hr_leave_view_kanban` |  |
| `views/leave_balance_views.xml` | `hr_leave_allocation_view_kanban_days_steelhouse` | `hr.leave.allocation` | extension | `hr_holidays.hr_leave_allocation_view_kanban` |  |
| `views/leave_report_views.xml` | `edit_holiday_status_form_sh_report` | `hr.leave.type` | extension | `hr_holidays.edit_holiday_status_form` |  |
| `views/mandatory_day_views.xml` | `hr_leave_mandatory_day_view_form_sh_monthly` | `hr.leave.mandatory.day` | extension | `hr_holidays.hr_leave_mandatory_day_view_form` |  |
| `views/mandatory_day_views.xml` | `hr_leave_mandatory_day_view_list_sh_monthly` | `hr.leave.mandatory.day` | extension | `hr_holidays.hr_leave_mandatory_day_view_list` |  |
| `views/mandatory_day_views.xml` | `hr_leave_mandatory_day_view_search_sh_monthly` | `hr.leave.mandatory.day` | extension | `hr_holidays.hr_leave_mandatory_day_view_search` |  |
| `views/res_users_views.xml` | `view_users_form_simple_modif_steelhouse` | `res.users` | extension | `mail.view_users_form_simple_modif_mail` |  |
| `views/res_users_views.xml` | `view_users_form_steelhouse` | `res.users` | extension | `mail.view_users_form_mail` |  |
| `views/res_users_views.xml` | `mail_activity_view_tree_steelhouse` | `mail.activity` | extension | `mail.mail_activity_view_tree` |  |

### Module `steelhouse_project`

| file | xml id | model | type | inherits | groups |
|---|---|---|---|---|---|
| `views/project_task_views.xml` | `view_task_form_steelhouse` | `project.task` | extension | `project.view_task_form2` |  |
| `views/project_task_views.xml` | `view_task_list_steelhouse` | `project.task` | extension | `project.project_task_view_tree_main_base` |  |
| `views/project_task_views.xml` | `view_task_search_steelhouse` | `project.task` | extension | `project.view_task_search_form` |  |
| `wizard/task_extension_wizard_views.xml` | `view_task_extension_wizard_form` | `steelhouse.task.extension.wizard` | form |  |  |
| `wizard/task_reason_wizard_views.xml` | `view_task_reason_wizard_form` | `steelhouse.task.reason.wizard` | form |  |  |

## Security

Groups: no new groups. Used: `base.group_user`, `base.group_system`, `project.group_project_user`, `project.group_project_manager`, `hr_holidays.group_hr_holidays_user`.

`ir.model.access.csv`

| module | model | group | r | w | c | d |
|---|---|---|---|---|---|---|
| task_flow | `steelhouse.task.flow.wizard` | `project.group_project_user` | 1 | 1 | 1 | 1 |
| task_flow | `steelhouse.task.template.wizard` | `base.group_user` | 1 | 1 | 1 | 1 |
| task_flow | `steelhouse.task.final.wizard` | `base.group_user` | 1 | 1 | 1 | 1 |
| task_flow | `steelhouse.task.section` | `base.group_user` | 1 | 1 | 1 | 1 |
| task_flow | `sh.task.flow.event` | `base.group_system` | 1 | 1 | 1 | 1 |
| task_flow | `steelhouse.project.hold.wizard` | `project.group_project_user` | 1 | 1 | 1 | 1 |
| hr | `steelhouse.leave.delegation` | `base.group_user` | 1 | 1 | 1 | 1 |
| hr | `steelhouse.leave.balance` | `base.group_user` | 1 | 0 | 0 | 0 |
| project | `steelhouse.task.extension.request` | `project.group_project_user` | 1 | 1 | 1 | 0 |
| project | `steelhouse.task.extension.request` | `project.group_project_manager` | 1 | 1 | 1 | 1 |
| project | `steelhouse.task.reason.wizard` | `project.group_project_user` | 1 | 1 | 1 | 1 |
| project | `steelhouse.task.extension.wizard` | `project.group_project_user` | 1 | 1 | 1 | 1 |

Record rules

| xml id | model | scope | perms | domain (short) |
|---|---|---|---|---|
| `rule_sh_task_department` | `project.task` | global | read | all for project administrators / `sh_see_all_tasks`; else template, no project, created by me, `sh_job_viewer_ids`, `sh_party_user_ids in user.sh_see_user_all_ids`, department in `user.sh_see_department_all_ids` |
| `rule_sh_task_department_write` | `project.task` | global | write, unlink | all for project administrators; else template, no project, main responsible, performer, reviewer, creator, head of the task's department |
| `rule_sh_project_department` | `project.project` | global | read, write, unlink | all for project administrators / `sh_see_all_tasks`; else template, manager, member or head of the department, a job of mine in it, departments given to me |
| `rule_leave_balance_own` | `steelhouse.leave.balance` | `base.group_user` | - | `user_id = user` |
| `rule_leave_balance_officer` | `steelhouse.leave.balance` | `hr_holidays.group_hr_holidays_user` | - | all |
| `rule_hr_leave_co_head` | `hr.leave` | `base.group_user` | - | `employee_id.sh_head_user_ids` contains me, validation by manager |
| `rule_hr_leave_allocation_co_head_read` | `hr.leave.allocation` | - | read | `employee_id.sh_head_user_ids` contains me |
| `rule_hr_leave_deputy_read` | `hr.leave` | - | read | I am a deputy in `delegation_ids` |

## Integrations

- No external systems. Outgoing e-mail is not configured (SMTP pending); notifications go through Odoo Discuss.
- Controllers: `steelhouse_hr/controllers/org_chart.py` (overrides two `hr_org_chart` routes), `controllers/thread.py` (overrides `_get_thread_with_access_for_post`, no route of its own).

## Scheduled jobs

| xml id | module | every | method |
|---|---|---|---|
| `ir_cron_sh_repeat` | task_flow | 1 h | `_cron_sh_repeat()` |
| `ir_cron_sh_overdue_notify` | task_flow | 1 h | `_cron_sh_overdue_notify()` |
| `ir_cron_sh_weekly_digest` | task_flow | 1 day | `_cron_sh_weekly_digest()` |
| `ir_cron_sh_place_personal` | task_flow | 1 day | `_cron_sh_place_personal()` |
| `cron_sync_leave_approvals` | hr | 1 h | `_sh_sync_approval_activities()` |
| `cron_quarter_allocations` | hr | 1 day | `_sh_sync_quarter_allocations()` |
| `cron_mandatory_days_monthly` | hr | 1 day | `_sh_generate_monthly()` |
| `ir_cron_deadline_notifications` | project (not installed) | - | - |

Server cron (outside Odoo): `/etc/cron.d/steelhouse-backup` - backup 02:00 daily, restore test on the 2nd of each month 03:30 (`deploy/backup/`).

## Migration / data

| module | version | script | what |
|---|---|---|---|
| task_flow | 19.0.1.13.0 | `pre-migrate.py` | see the script |
| task_flow | 19.0.1.56.0 - 58.0 | `post-migrate.py` | see the scripts |
| task_flow | 19.0.1.144.0 | `post-migrate.py` | see the script |
| task_flow | 19.0.1.176.0 | `post-migrate.py` | extra viewers of the old confidential tasks carried over to `sh_extra_viewer_ids` |
| task_flow | 19.0.1.177.0 | - | new column `sh_start_request_date`, empty on existing tasks |
| hr | 19.0.1.38.0, 46.0, 54.0 | `post-migrate.py` | see the scripts |

One-off data scripts: `deploy/setup_*.py` (Odoo shell). The client's visibility list: `deploy/setup_task_visibility.py`.

## Tests

No automated tests (D-8). Each change is checked by hand on the live server, in the demo department "სადემონსტრაციო განყოფილება" with users `demo.manager` / `demo.employee` / `demo.employee2`.
The recording scripts in `deploy/manual_video/` act as scripted checks of the flows below (they stop with an error when a step does not behave as written):

| AC | script | what it asserts |
|---|---|---|
| AC-1, AC-2, AC-3, AC-11 | `v1_employee.py` | accept -> `accepted`, stage bar -> `in_progress`, done -> `review`, hold with a reason -> `on_hold` (stage read back over RPC) |
| AC-3, AC-4 | `v3_reviewer.py` + `v3_play.py` | approve -> `done`, reject with a reason -> `returned`, resume -> `new`, cancel -> `cancelled` |
| AC-6, AC-7, AC-8, AC-9 | `v4_sequence.py` | step dragged into another step lands in that column; `depend_on_ids` equal the planned ones (`tidy`) |
| AC-10, AC-12 | `v4_sequence.py` | `sh_start_request_date` set after the request; `sh_continue_ok` set after "შემდეგის დაშვება"; next step accepted |
| AC-5, AC-13, AC-14, AC-15, AC-16 | - | not covered by a script |

## Traceability

| AC | models / fields | check |
|---|---|---|
| AC-1 | `project.task` personal stages, `task_personal.py` | `v1_employee.py` |
| AC-2, AC-3 | `project.task.type.sh_kind`, `action_sh_accept`, `action_sh_mark_done` | `v1_employee.py` |
| AC-4, AC-5 | `reviewer_ids`, `return_reason`, `sh_approval_reject` | `v3_play.py` (AC-5: none) |
| AC-6, AC-7 | `depend_on_ids`, `_sh_check_not_waiting`, `_sh_open_before_review` | `v4_sequence.py` |
| AC-8 | `sh_parallel_ids`, `sh_chain_move` | `v4_sequence.py` |
| AC-9 | `sh_card_list('chain')`, `sh_step_badge` | `v4_sequence.py` |
| AC-10, AC-11 | `sh_continue_ok`, `sh_prev_held`, `action_sh_allow_next`, `task_hold.py` | `v4_sequence.py`, `v1_employee.py` |
| AC-12 | `sh_start_request_date`, `sh_can_request_start`, `action_sh_request_start` | `v4_sequence.py` |
| AC-13, AC-14 | `sh_party_user_ids`, `sh_job_viewer_ids`, `res.users.sh_see_*`, `rule_sh_task_department*` | none |
| AC-15 | `task_reports.py`, `task_pdf.py` | none |
| AC-16 | `hr.leave`, `steelhouse.leave.delegation`, `leave_approval_flow.py` | none |
| AC-17 | `deploy/manual_video/` | frames checked by hand |

## Open questions
1. Standard-first rows marked "not recorded": the reason for custom code was not written down at the time.
2. Migration scripts before 176 are listed without a description - read the script before relying on it.
3. `sh.task.flow.event` and `steelhouse.task.section` do not follow the same model prefix.
