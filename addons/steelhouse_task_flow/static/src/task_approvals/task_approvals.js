import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TABS = [
    { key: "todo", label: "ჩემი დასადასტურებელი" },
    { key: "sent", label: "ჩემი გაგზავნილი" },
    { key: "history", label: "ისტორია" },
];

// "დასადასტურებელი": tasks on "შემოწმებაზე" that wait for me as a reviewer (models/task_approvals.py).
// Confirm -> done; reject -> back to the assignee, the reason is required.
export class TaskApprovals extends Component {
    static template = "steelhouse_task_flow.TaskApprovals";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.TABS = TABS;
        this.state = useState({
            tab: "todo",
            data: null,
            search: "",
            loading: true,
            dialog: null, // { mode: "ok" | "no", item, reason, error, busy }
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("project.task", "sh_approvals_data", [], { tab: this.state.tab });
        this.state.loading = false;
    }
    setTab(tab) {
        this.state.tab = tab;
        this.state.search = "";
        this.load();
    }
    onSearch(ev) {
        this.state.search = ev.target.value;
    }
    matches(row) {
        const q = this.state.search.trim().toLowerCase();
        return !q || [row.number, row.name, row.users, row.department, row.project, row.reason]
            .some((v) => (v || "").toLowerCase().includes(q));
    }
    get items() {
        return this.state.data.items.filter((i) => this.matches(i));
    }
    get history() {
        return this.state.data.history.filter((h) => this.matches(h));
    }
    count(tab) {
        const counts = this.state.data && this.state.data.counts;
        return counts && counts[tab] !== undefined ? counts[tab] : null;
    }

    openTask(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------------------------------------------------------- decisions
    ask(mode, item) {
        this.state.dialog = { mode, item, reason: "", error: "", busy: false };
    }
    closeDialog() {
        if (!this.state.dialog.busy) {
            this.state.dialog = null;
        }
    }
    onReason(ev) {
        this.state.dialog.reason = ev.target.value;
        this.state.dialog.error = "";
    }
    async confirm() {
        const dlg = this.state.dialog;
        if (dlg.busy) {
            return;
        }
        if (dlg.mode === "no" && !dlg.reason.trim()) {
            dlg.error = "მიუთითეთ მიზეზი - მის გარეშე უარყოფა არ შეიძლება.";
            return;
        }
        dlg.busy = true;
        try {
            if (dlg.mode === "ok") {
                await this.orm.call("project.task", "sh_approval_approve", [[dlg.item.id]]);
            } else {
                await this.orm.call("project.task", "sh_approval_reject", [[dlg.item.id], dlg.reason.trim()]);
            }
        } finally {
            // on an error Odoo shows its own message; the list is refreshed either way
            this.state.dialog = null;
            await this.load();
        }
    }
}

registry.category("actions").add("sh_task_approvals", TaskApprovals);
