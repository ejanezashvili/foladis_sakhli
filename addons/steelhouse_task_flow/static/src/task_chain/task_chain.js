import { Component, onWillStart, useRef, useState } from "@odoo/owl";
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
const POP_W = 300; // "add a step" pop-up card
const POP_H = 400;

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
            drag: null,
            drop: null,
        });
        this.scrollRef = useRef("scroll");
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
    // the pop-up opens where "+" was clicked: right of the anchor task ("next") or at the start ("prev")
    get popPos() {
        const p = this.state.form || this.state.link;
        if (!p) {
            return null;
        }
        const anchor = this.layout.pos[p.anchor_id];
        const y = anchor ? anchor.y : PAD + HEAD;
        const x = p.direction === "prev" ? PAD : anchor ? anchor.x + W + 14 : this.layout.endX;
        return { x, y };
    }
    get popStyle() {
        const p = this.popPos;
        return p ? `left:${p.x}px;top:${p.y}px;width:${POP_W}px;` : "";
    }
    get canvasStyle() {
        const lay = this.layout;
        const p = this.popPos;
        const w = p ? Math.max(lay.width, p.x + POP_W + PAD) : lay.width;
        const h = p ? Math.max(lay.height, p.y + POP_H + PAD) : lay.height;
        return `width:${w}px;height:${h}px;`;
    }
    scrollToPop() {
        setTimeout(() => {
            const el = this.scrollRef.el;
            const p = this.popPos;
            if (el && p) {
                el.scrollTo({ left: Math.max(0, p.x + POP_W - el.clientWidth + PAD), behavior: "smooth" });
                el.querySelector(".o_sh_chain_pop input")?.focus();
            }
        }, 50);
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

    onCardClick(node) {
        if (node.current) {
            return;
        }
        if (this.state.readonly) {
            return this.openTask(node);
        }
        return this.openEdit(node);
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
            parallel: false,
            parallel_ids: [],
        };
        await this.loadUsers();
        this.scrollToPop();
    }
    // edit a task of the chain in the same pop-up
    async openEdit(node) {
        this.state.link = null;
        if (!this.state.departments.length) {
            this.state.departments = await this.orm.call("project.task", "sh_chain_departments", []);
        }
        const v = await this.call("sh_chain_task_get", [node.id]);
        this.state.form = {
            mode: "edit",
            task_id: node.id,
            node,
            direction: "next",
            anchor_id: node.id,
            anchor_name: node.name,
            step: node.level + 1,
            name: v.name,
            project_id: v.project_id,
            user_id: v.user_id,
            reviewer_ids: v.reviewer_ids,
            reviewerPick: 0,
            editReviewers: false,
            deadline: v.deadline,
            subtasks: [],
            parallel: false,
            parallel_ids: [],
        };
        await this.loadUsers();
        this.scrollToPop();
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
    // parallel task: runs alongside the chosen tasks of this sequence (same previous / next tasks)
    toggleParallel(ev) {
        const f = this.state.form;
        f.parallel = ev.target.checked;
        if (f.parallel && !f.parallel_ids.length && this.state.nodes.some((n) => n.id === f.anchor_id)) {
            f.parallel_ids = [f.anchor_id];
        }
    }
    toggleParallelTask(id) {
        const f = this.state.form;
        f.parallel_ids = f.parallel_ids.includes(id) ? f.parallel_ids.filter((x) => x !== id) : [...f.parallel_ids, id];
    }
    get parallelStep() {
        const levels = this.state.nodes.filter((n) => this.state.form.parallel_ids.includes(n.id)).map((n) => n.level + 1);
        return [...new Set(levels)].sort((a, b) => a - b).join(", ");
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
        if (f.parallel && !f.parallel_ids.length) {
            this.notification.add("მონიშნეთ, რომელი დავალებების პარალელურია.", { type: "warning" });
            return;
        }
        if (!f.reviewer_ids.length) {
            this.notification.add("მიუთითეთ შემმოწმებელი.", { type: "warning" });
            return;
        }
        this.state.busy = true;
        if (f.mode === "edit") {
            try {
                await this.call("sh_chain_task_write", [
                    f.task_id,
                    { name: f.name, project_id: f.project_id, user_id: f.user_id || false,
                      reviewer_ids: f.reviewer_ids, deadline: f.deadline || false },
                ]);
                this.state.form = null;
                this.notification.add("ცვლილებები შენახულია.", { type: "success" });
                await this.refresh();
            } finally {
                this.state.busy = false;
            }
            return;
        }
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
                    parallel_ids: f.parallel ? f.parallel_ids : [],
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
    // ---------------------------------------------------------- drag & drop
    // drop on a step's column: the task joins that step (in parallel);
    // drop in the gap between steps (or before the first / after the last): it becomes a new step there
    get canDrag() {
        return !this.state.readonly && !this.state.form && !this.state.link && this.state.nodes.length > 1;
    }
    onDragStart(ev, node) {
        if (!this.canDrag) {
            ev.preventDefault();
            return;
        }
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(node.id));
        this.state.drag = { id: node.id, level: node.level };
    }
    onDragEnd() {
        this.state.drag = null;
        this.state.drop = null;
    }
    dropTarget(ev) {
        const rect = ev.currentTarget.getBoundingClientRect();
        const x = ev.clientX - rect.left;
        const cols = this.layout.cols;
        for (let l = 0; l < cols; l++) {
            const left = this.colX(l);
            if (x >= left && x <= left + W) {
                return { mode: "into", level: l };
            }
            if (x < left) {
                return { mode: "before", level: l };
            }
        }
        return { mode: "before", level: cols };
    }
    isNoop(target) {
        const drag = this.state.drag;
        if (!drag || !target) {
            return true;
        }
        const alone = !this.state.nodes.some((n) => n.level === drag.level && n.id !== drag.id);
        if (target.mode === "into") {
            return target.level === drag.level;
        }
        return alone && (target.level === drag.level || target.level === drag.level + 1);
    }
    onDragOver(ev) {
        if (!this.state.drag) {
            return;
        }
        ev.preventDefault();
        const t = this.dropTarget(ev);
        const drop = this.isNoop(t) ? null : t;
        const cur = this.state.drop;
        if (!cur !== !drop || (cur && (cur.mode !== drop.mode || cur.level !== drop.level))) {
            this.state.drop = drop;
        }
        ev.dataTransfer.dropEffect = drop ? "move" : "none";
    }
    async onDrop(ev) {
        ev.preventDefault();
        const drag = this.state.drag;
        const drop = this.state.drop;
        this.onDragEnd();
        if (!drag || !drop) {
            return;
        }
        this.state.busy = true;
        try {
            await this.call("sh_chain_move", [drag.id, drop.mode, drop.level]);
            await this.refresh();
        } finally {
            this.state.busy = false;
        }
    }
    get dropStyle() {
        const d = this.state.drop;
        if (!d) {
            return "";
        }
        const top = PAD + HEAD - 8;
        const height = this.layout.height - top - 4;
        if (d.mode === "into") {
            return `left:${this.colX(d.level) - 8}px;top:${top}px;width:${W + 16}px;height:${height}px;`;
        }
        const x = d.level === 0 ? PAD + SLOT + GX / 2 : this.colX(d.level) - GX / 2;
        return `left:${x - 3}px;top:${top}px;width:6px;height:${height}px;`;
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
