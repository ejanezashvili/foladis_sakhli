import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { user } from "@web/core/user";
import { ShUserPicker } from "../task_steps/task_steps";

// card size and gaps of the chain diagram (px)
const W = 236;
const H = 124;
const GX = 70;
const GY = 18;
const PAD = 10;

// "თანმიმდევრობა" tab: tasks that follow one another (any department), joined by arrows.
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
        this.state = useState({
            loaded: false,
            nodes: [],
            edges: [],
            prev: [],
            next: [],
            readonly: false,
            truncated: false,
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
            prev: data.prev || [],
            next: data.next || [],
            readonly: data.readonly,
            truncated: data.truncated,
            loaded: true,
        });
    }

    async refresh() {
        await this.load();
        await this.props.record.load();
    }

    // ---------------------------------------------------------- layout
    get layout() {
        const pos = {};
        const rows = {};
        for (const n of this.state.nodes) {
            const row = rows[n.level] || 0;
            rows[n.level] = row + 1;
            pos[n.id] = { x: PAD + n.level * (W + GX), y: PAD + row * (H + GY) };
        }
        const cols = Math.max(0, ...Object.keys(rows).map((l) => Number(l) + 1));
        const maxRows = Math.max(0, ...Object.values(rows));
        return {
            pos,
            width: PAD * 2 + cols * W + Math.max(0, cols - 1) * GX,
            height: PAD * 2 + maxRows * H + Math.max(0, maxRows - 1) * GY,
        };
    }
    get hasChain() {
        return this.state.nodes.length > 1;
    }
    cardStyle(node) {
        const p = this.layout.pos[node.id];
        return `left:${p.x}px;top:${p.y}px;width:${W}px;height:${H}px;`;
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
                    d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`,
                    done,
                };
            });
    }
    statusLabel(node) {
        return {
            done: "შესრულდა",
            cancelled: "გაუქმდა",
            waiting: "ელოდება წინას",
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
    avatar(id) {
        return `/web/image/res.users/${id}/avatar_128`;
    }
    nodesOf(ids) {
        return this.state.nodes.filter((n) => ids.includes(n.id));
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

    // ---------------------------------------------------------- new task
    async openForm(direction) {
        this.state.link = null;
        if (!this.state.departments.length) {
            this.state.departments = await this.orm.call("project.task", "sh_chain_departments", []);
        }
        this.state.form = {
            direction,
            name: "",
            project_id: this.currentProjectId,
            user_id: false,
            reviewer_ids: [user.userId],
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
        // keep the chosen people only if they work in the new department
        const dept = this.state.deptUserIds || [];
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
        f.reviewerPick = (f.reviewerPick || 0) + 1; // reset the picker
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
            ]);
            this.state.form = null;
            this.notification.add(
                f.direction === "next" ? "შემდეგი დავალება შეიქმნა." : "წინა დავალება შეიქმნა.",
                { type: "success" }
            );
            await this.refresh();
        } finally {
            this.state.busy = false;
        }
    }

    // ---------------------------------------------------------- link existing
    async openLink(direction) {
        this.state.form = null;
        this.state.link = { direction, term: "", results: [] };
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
        await this.call("sh_chain_link", [this.state.link.direction, item.id]);
        this.state.link = null;
        await this.refresh();
    }
    unlink(direction, node) {
        this.dialog.add(ConfirmationDialog, {
            title: "დარწმუნებული ხარ?",
            body: `„${node.name}“ აღარ იქნება ${direction === "next" ? "შემდეგი" : "წინა"} დავალება (თვითონ დავალება არ წაიშლება).`,
            confirmLabel: "კი, მოიხსნას",
            cancelLabel: "არა",
            confirm: async () => {
                await this.call("sh_chain_unlink", [direction, node.id]);
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
