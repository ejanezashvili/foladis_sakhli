import { patch } from "@web/core/utils/patch";
import { TimeOffCard } from "@hr_holidays/dashboard/time_off_card";

// "+ New request" on a time off type card: the usual new time off window,
// with this type already chosen; the cards are refreshed afterwards.
patch(TimeOffCard.prototype, {
    shNewLeave() {
        const context = {
            default_holiday_status_id: this.props.holidayStatusId,
            form_view_ref: "hr_holidays.hr_leave_view_form_dashboard_new_time_off",
        };
        if (this.props.employeeId) {
            context.default_employee_id = this.props.employeeId;
        }
        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                name: this.props.name,
                res_model: "hr.leave",
                views: [[false, "form"]],
                target: "new",
                context,
            },
            {
                onClose: () => this.env.timeOffBus?.trigger("update_dashboard"),
            }
        );
    },
});
