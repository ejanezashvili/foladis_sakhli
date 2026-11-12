import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { user } from "@web/core/user";
import { ShUserPicker } from "../task_steps/task_steps";

// sizes of the step diagram (px)
const W = 236; // card
const H = 116;
const GX = 74; // gap between steps (arrows)
const GY = 18;
const PAD = 12;
const HEAD = 40; // row with the step numbers
const SLOT = 96; // "+ before" / "+ after" boxes
const SLOT_H = 44;

// "თანმიმდევრობა" tab: tasks as numbered steps 1 → 2 → 3 ... (any department), joined by arrows.
// Tasks of the same step run in parallel; a step starts when its previous tasks are finished.
export class TaskChain extends Component {
    static template = "steelhouse_task_flow.TaskChain";
    static props = { ...standardFieldProps };
    static components = { ShUserPicker };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.W = W;
        this.H = H;
        this.SLOT = SLOT;
        this.state = useState({
            loaded: false,
            nodes: [],
            edges: [],
            readonly: false,
            truncated: false,
            project: "",
            departments: [],
            form: null,
            users: [],
            deptUserIds: [],
            link: null,
            busy: false,
        });
        onWillStart(() => this.load());
    }

    get taskId() {
        return this.props.record.resId;
    }
    get currentProjectId() {
        const p = this.props.record.data.project_id;
        return (p && (p.id || p[0])) || false;
    }

    async call(method, args = []) {
        return this.orm.call("project.task", method, [[this.taskId], ...args]);
    }

    async load() {
        if (!this.taskId) {
            this.state.loaded = true;
            return;
        }
        const data = await this.call("sh_chain_data");
        Object.assign(this.state, {
            nodes: data.nodes,
            edges: data.edges,
            readonly: data.readonly,
            truncated: data.truncated,
            project: data.project || "",
            loaded: true,
        });
    }

    async refresh() {
        await this.load();
        await this.props.record.load();
    }

    // ---------------------------------------------------------- layout
    colX(level) {
        return PAD + SLOT + GX + level * (W + GX);
    }
    get steps() {
        const levels = [...new Set(this.state.nodes.map((n) => n.level))].sort((a, b) => a - b);
        return levels.map((l) => ({ level: l, number: l + 1, x: this.colX(l) + W / 2 }));
    }
    get layout() {
        const pos = {};
        const rows = {};
        for (const n of this.state.nodes) {
            const row = rows[n.level] || 0;
            rows[n.level] = row + 1;
            pos[n.id] = { x: this.colX(n.level), y: PAD + HEAD + row * (H + GY) };
        }
        const cols = Math.max(1, ...Object.keys(rows).map((l) => Number(l) + 1));
        const maxRows = Math.max(1, ...Object.values(rows));
        const lastX = this.colX(cols - 1) + W;
        return {
            pos,
            cols,
            endX: lastX + GX,
            width: lastX + GX + SLOT + PAD,
            height: PAD * 2 + HEAD + maxRows * H + (maxRows - 1) * GY,
        };
    }
    cardStyle(node) {
        const p = this.layout.pos[node.id];
        return `left:${p.x}px;top:${p.y}px;width:${W}px;height:${H}px;`;
    }
    get startSlotStyle() {
        return `left:${PAD}px;top:${PAD + HEAD + (H - SLOT_H) / 2}px;width:${SLOT}px;height:${SLOT_H}px;`;
    }
    get endSlotStyle() {
        return `left:${this.layout.endX}px;top:${PAD + HEAD + (H - SLOT_H) / 2}px;width:${SLOT}px;height:${SLOT_H}px;`;
    }
    // the first step's first task gets "+ previous step"; the last step's first task gets "+ step N"
    get firstNode() {
        const first = this.state.nodes.filter((n) => n.level === 0);
        return first.find((n) => n.current) || first[0];
    }
    get lastNode() {
        const maxLevel = Math.max(...this.state.nodes.map((n) => n.level));
        const last = this.state.nodes.filter((n) => n.level === maxLevel);
        return last.find((n) => n.current) || last[0];
    }
    arrows() {
        const pos = this.layout.pos;
        return this.state.edges
            .filter(([a, b]) => pos[a] && pos[b])
            .map(([a, b, done]) => {
                const x1 = pos[a].x + W;
                const y1 = pos[a].y + H / 2;
                const x2 = pos[b].x - 3;
                const y2 = pos[b].y + H / 2;
                const dx = Math.max(30, (x2 - x1) / 2);
                return {
                    key: `${a}-${b}`,
                    from: a,
                    to: b,
                    d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`,
                    done,
                    // ✕ button in the middle of the arrow
                    mx: (x1 + x2) / 2,
                    my: (y1 + y2) / 2,
                };
            });
    }
    statusLabel(node) {
        return {
            done: "შესრულდა",
            cancelled: "გაუქმდა",
            waiting: "ელოდება",
            active: node.stage || "აქტიური",
        }[node.status];
    }
    statusIcon(node) {
        return {
            done: "fa-check-circle",
            cancelled: "fa-ban",
            waiting: "fa-lock",
            active: "fa-play-circle",
        }[node.status];
    }
    stepState(level) {
        const nodes = this.state.nodes.filter((n) => n.level === level && n.status !== "cancelled");
        if (nodes.length && nodes.every((n) => n.status === "done")) {
            return "done";
        }
        return nodes.some((n) => n.status === "active") ? "active" : "waiting";
    }
    avatar(id) {
        return `/web/image/res.users/${id}/avatar_128`;
    }
    nodeName(id) {
        const n = this.state.nodes.find((x) => x.id === id);
        return n ? n.name : "";
    }

    async openTask(node) {
        if (node.current) {
            return;
        }
        if (!node.can_open) {
            this.notification.add("ამ დავალების გახსნის უფლება არ გაქვთ.", { type: "warning" });
            return;
        }
        if (await this.props.record.save()) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "project.task",
                res_id: node.id,
                views: [[false, "form"]],
            });
        }
    }

    // ---------------------------------------------------------- new step
    // anchor: the task the new one goes before ('prev') or after ('next')
    async openForm(direction, anchor) {
        this.state.link = null;
        if (!this.state.departments.length) {
            this.state.departments = await this.orm.call("project.task", "sh_chain_departments", []);
        }
        const level = anchor ? anchor.level : 0;
        this.state.form = {
            direction,
            anchor_id: anchor ? anchor.id : this.taskId,
            anchor_name: anchor ? anchor.name : "",
            step: direction === "next" ? level + 2 : Math.max(1, level),
            name: "",
            project_id: this.currentProjectId,
            user_id: false,
            reviewer_ids: [user.userId],
            reviewerPick: 0,
            editReviewers: false,
            deadline: "",
            subtasks: [],
        };
        await this.loadUsers();
    }
    async loadUsers() {
        const res = await this.orm.call("project.task", "sh_chain_users", [this.state.form.project_id || false]);
        this.state.users = [...res.department, ...res.others];
        this.state.deptUserIds = res.department.map((u) => u.id);
    }
    async onDepartment(ev) {
        this.state.form.project_id = Number(ev.target.value) || false;
        await this.loadUsers();
        const dept = this.state.deptUserIds;
        if (this.state.form.user_id && dept.length && !dept.includes(this.state.form.user_id)) {
            this.state.form.user_id = false;
        }
    }
    userName(id) {
        const u = this.state.users.find((x) => x.id === id);
        return u ? u.name : "";
    }
    addReviewer(id) {
        const f = this.state.form;
        if (id && !f.reviewer_ids.includes(id)) {
            f.reviewer_ids.push(id);
        }
        f.reviewerPick++; // reset the picker
    }
    removeReviewer(id) {
        this.state.form.reviewer_ids = this.state.form.reviewer_ids.filter((r) => r !== id);
    }
    addSub() {
        this.state.form.subtasks.push({ key: Date.now() + Math.random(), name: "", user_id: false, deadline: "" });
    }
    removeSub(sub) {
        this.state.form.subtasks = this.state.form.subtasks.filter((s) => s !== sub);
    }
    cancelForm() {
        this.state.form = null;
    }
    async saveForm() {
        const f = this.state.form;
        if (!f.name.trim()) {
            this.notification.add("ჩაწერეთ დავალების სახელი.", { type: "warning" });
            return;
        }
        if (!f.project_id) {
            this.notification.add("აირჩიეთ დეპარტამენტი.", { type: "warning" });
            return;
        }
        if (!f.reviewer_ids.length) {
            this.notification.add("მიუთითეთ შემმოწმებელი.", { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            await this.call("sh_chain_create", [
                f.direction,
                {
                    name: f.name,
                    project_id: f.project_id,
                    user_id: f.user_id || false,
                    reviewer_ids: f.reviewer_ids,
                    deadline: f.deadline || false,
                    subtasks: f.subtasks.map((s) => ({ name: s.name, user_id: s.user_id || false, deadline: s.deadline || false })),
                },
                f.anchor_id,
            ]);
            this.state.form = null;
            this.notification.add("ნაბიჯი დაემატა.", { type: "success" });
            await this.refresh();
        } finally {
            this.state.busy = false;
        }
    }

    // ---------------------------------------------------------- link existing
    async openLinkFromForm() {
        const f = this.state.form;
        this.state.form = null;
        this.state.link = { direction: f.direction, anchor_id: f.anchor_id, anchor_name: f.anchor_name, step: f.step, term: "", results: [] };
        await this.search();
    }
    async search() {
        const link = this.state.link;
        link.results = await this.call("sh_chain_search", [link.term]);
    }
    onLinkTerm(ev) {
        this.state.link.term = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.search(), 250);
    }
    async pickLink(item) {
        const link = this.state.link;
        await this.call("sh_chain_link", [link.direction, item.id, link.anchor_id]);
        this.state.link = null;
        await this.refresh();
    }
    unlinkEdge(arrow) {
        this.dialog.add(ConfirmationDialog, {
            title: "დარწმუნებული ხარ?",
            body: `„${this.nodeName(arrow.from)}“ → „${this.nodeName(arrow.to)}“ - კავშირი მოიხსნება (დავალებები არ წაიშლება).`,
            confirmLabel: "კი, მოიხსნას",
            cancelLabel: "არა",
            confirm: async () => {
                await this.call("sh_chain_unlink_edge", [arrow.from, arrow.to]);
                await this.refresh();
            },
            cancel: () => {},
        });
    }
}

registry.category("fields").add("sh_task_chain", {
    component: TaskChain,
    supportedTypes: ["char"],
});
