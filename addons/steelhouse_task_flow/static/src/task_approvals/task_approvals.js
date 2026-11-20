import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TABS = [
    { key: "todo", label: "ჩემი დასადასტურებელი" },
    { key: "sent", label: "ჩემი გაგზავნილი" },
    { key: "history", label: "ისტორია" },
];

// "დადასტურებები": tasks on "შემოწმებაზე" that wait for me as a reviewer (models/task_approvals.py).
// Outside - the queue (long waiting first); inside - the review page of one task.
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
            detail: null, // review page: { id, data, loading, reason, error, busy }
        });
        this.descMarkup = "";
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
    // long waiting first, then the fresh ones
    get groups() {
        const items = this.items;
        return [
            { key: "late", label: "დიდხანს ელოდება", late: true, items: items.filter((i) => i.late) },
            { key: "new", label: "ახალი", late: false, items: items.filter((i) => !i.late) },
        ].filter((g) => g.items.length);
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

    // ---------------------------------------------------------------- review page (inside)
    async openReview(id) {
        this.descMarkup = "";
        this.state.detail = { id, data: null, loading: true, reason: "", error: "", busy: false };
        try {
            const data = await this.orm.call("project.task", "sh_approval_detail", [[id]]);
            this.descMarkup = data.description ? markup(data.description) : "";
            this.state.detail.data = data;
            this.state.detail.loading = false;
        } catch (e) {
            this.state.detail = null;
            throw e;
        }
    }
    closeReview() {
        this.state.detail = null;
    }
    // position of the opened task in the list on screen (-1: opened from the history)
    get reviewIndex() {
        const id = this.state.detail.id;
        return this.state.tab === "history" ? -1 : this.items.findIndex((i) => i.id === id);
    }
    get reviewPosition() {
        return `${this.reviewIndex + 1} / ${this.items.length}`;
    }
    get hasPrev() {
        return this.reviewIndex > 0;
    }
    get hasNext() {
        const idx = this.reviewIndex;
        return idx >= 0 && idx < this.items.length - 1;
    }
    reviewStep(delta) {
        const next = this.items[this.reviewIndex + delta];
        if (next) {
            this.openReview(next.id);
        }
    }
    onDetailReason(ev) {
        this.state.detail.reason = ev.target.value;
        this.state.detail.error = "";
    }
    // the task to show after a decision made on the review page: the next one, else the previous
    neighbourId(id) {
        const list = this.items;
        const idx = list.findIndex((i) => i.id === id);
        const other = idx >= 0 ? list[idx + 1] || list[idx - 1] : null;
        return other ? other.id : null;
    }
    async afterDecision(id, done, nextId) {
        await this.load();
        if (this.state.detail && this.state.detail.id === id) {
            if (done && nextId && this.items.some((i) => i.id === nextId)) {
                await this.openReview(nextId);
            } else if (done) {
                this.closeReview();
            } else {
                await this.openReview(id);
            }
        }
    }
    async rejectInside() {
        const det = this.state.detail;
        if (det.busy) {
            return;
        }
        const reason = det.reason.trim();
        if (!reason) {
            det.error = "მიუთითეთ მიზეზი - მის გარეშე უარყოფა არ შეიძლება.";
            return;
        }
        det.busy = true;
        const nextId = this.neighbourId(det.id);
        let done = false;
        try {
            await this.orm.call("project.task", "sh_approval_reject", [[det.id], reason]);
            done = true;
        } finally {
            det.busy = false;
            await this.afterDecision(det.id, done, nextId);
        }
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
        const id = dlg.item.id;
        const nextId = this.neighbourId(id);
        let done = false;
        try {
            if (dlg.mode === "ok") {
                await this.orm.call("project.task", "sh_approval_approve", [[id]]);
            } else {
                await this.orm.call("project.task", "sh_approval_reject", [[id], dlg.reason.trim()]);
            }
            done = true;
        } finally {
            // on an error Odoo shows its own message; the list is refreshed either way
            this.state.dialog = null;
            await this.afterDecision(id, done, nextId);
        }
    }
}

registry.category("actions").add("sh_task_approvals", TaskApprovals);
