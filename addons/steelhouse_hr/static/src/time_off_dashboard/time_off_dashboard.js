import { patch } from "@web/core/utils/patch";
import { TimeOffDashboard } from "@hr_holidays/dashboard/time_off_dashboard";

// Approvers see on their own dashboard how many time off requests wait for them
// (the standard "Pending Requests" card counts only their own allocation requests).
patch(TimeOffDashboard.prototype, {
    setup() {
        super.setup();
        this.state.shToApprove = -1;
    },

    async loadDashboardData() {
        await super.loadDashboardData(...arguments);
        if (this.props.employeeId) {
            return;
        }
        this.state.shToApprove = await this.orm.call("hr.leave", "sh_waiting_for_me_count", []);
    },

    openToApprove() {
        this.actionService.doAction("hr_holidays.hr_leave_action_action_approve_department");
    },
});
