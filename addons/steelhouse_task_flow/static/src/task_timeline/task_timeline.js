import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DAY = 86400000;
const LABEL_W = 320;
const MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი", "ივლისი",
    "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
const WEEKDAYS = ["კვ", "ორ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ"];
const SCALES = {
    week: { label: "2 კვირა", dayW: 84 },
    month: { label: "თვე", dayW: 38 },
    quarter: { label: "3 თვე", dayW: 13 },
};
export const KINDS = {
    new: "ახალი",
    accepted: "მიღებული",
    in_progress: "მიმდინარე",
    on_hold: "შეჩერებული",
    review: "შემოწმებაზე",
    returned: "დაბრუნებული",
    done: "დასრულებული",
    cancelled: "გაუქმებული",
};
const VIEWS = [
    { key: "timeline", label: "Timeline", icon: "fa-align-left" },
    { key: "user", label: "ინდივიდუალური დატვირთვა", icon: "fa-user" },
    { key: "team", label: "გუნდური დატვირთვა", icon: "fa-users" },
];
// workload colors: open tasks running at the same time (per person for the team view)
const LOAD_STEPS = [
    [0, ""],
    [2, "o_sh_wl_ok"],
    [4, "o_sh_wl_busy"],
    [Infinity, "o_sh_wl_over"],
];
const PRIORITY = { 0: "დაბალი", 1: "საშუალო", 2: "მაღალი", 3: "კრიტიკული" };

// dates are handled as UTC midnights of 'YYYY-MM-DD' strings (no time zone shifts)
const parse = (s) => new Date(s + "T00:00:00Z");
const iso = (d) => d.toISOString().slice(0, 10);
const addDays = (d, n) => new Date(d.getTime() + n * DAY);
const fmt = (s) => (s ? s.slice(8, 10) + "." + s.slice(5, 7) + "." + s.slice(0, 4) : "-");

// "Timeline": tasks as bars from the start (work start / creation) to the deadline, grouped by
// department / employee / project. Overdue tasks get a red tail up to today.
export class TaskTimeline extends Component {
    static template = "steelhouse_task_flow.TaskTimeline";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // narrower name column on phones
        this.LABEL_W = window.innerWidth < 768 ? 170 : LABEL_W;
        this.SCALES = SCALES;
        this.scaleKeys = Object.keys(SCALES);
        this.KINDS = KINDS;
        this.VIEWS = VIEWS;
        this.state = useState({
            view: "timeline",
            scope: "mine",
            detail: false,
            showDone: false,
            work: null,
            scale: "month",
            anchor: this.today(),
            groupBy: "department",
            status: "open",
            departmentId: "",
            userId: "",
            search: "",
            subtasks: false,
            data: null,
            loading: true,
            expanded: {}, // "ყველა": groups start folded
        });
        onWillStart(() => this.load());
    }

    today() {
        const n = new Date();
        return new Date(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()));
    }

    // ---------------------------------------------------------------- period
    get range() {
        const a = this.state.anchor;
        if (this.state.scale === "week") {
            const from = addDays(a, -((a.getUTCDay() + 6) % 7)); // Monday
            return { from, to: addDays(from, 13) };
        }
        if (this.state.scale === "quarter") {
            const m = a.getUTCMonth() - (a.getUTCMonth() % 3);
            return {
                from: new Date(Date.UTC(a.getUTCFullYear(), m, 1)),
                to: new Date(Date.UTC(a.getUTCFullYear(), m + 3, 0)),
            };
        }
        return {
            from: new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth(), 1)),
            to: new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() + 1, 0)),
        };
    }
    get days() {
        return Math.round((this.range.to - this.range.from) / DAY) + 1;
    }
    get dayW() {
        return SCALES[this.state.scale].dayW;
    }
    get width() {
        return this.days * this.dayW;
    }
    get periodLabel() {
        const { from, to } = this.range;
        if (this.state.scale === "month") {
            return `${MONTHS[from.getUTCMonth()]} ${from.getUTCFullYear()}`;
        }
        if (this.state.scale === "quarter") {
            return `${MONTHS[from.getUTCMonth()]} - ${MONTHS[to.getUTCMonth()]} ${to.getUTCFullYear()}`;
        }
        return `${fmt(iso(from))} - ${fmt(iso(to))}`;
    }
    idx(s) {
        return Math.round((parse(s) - this.range.from) / DAY);
    }

    get months() {
        const out = [];
        let d = this.range.from;
        while (d <= this.range.to) {
            const end = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0));
            const last = end < this.range.to ? end : this.range.to;
            const span = Math.round((last - d) / DAY) + 1;
            out.push({
                key: iso(d),
                label: `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`,
                style: `left:${Math.round((d - this.range.from) / DAY) * this.dayW}px;width:${span * this.dayW}px`,
            });
            d = addDays(last, 1);
        }
        return out;
    }
    get dayCells() {
        const out = [];
        const off = new Set((this.state.data && this.state.data.off_days) || []);
        const today = this.state.data && this.state.data.today;
        for (let i = 0; i < this.days; i++) {
            const d = addDays(this.range.from, i);
            const s = iso(d);
            const wd = d.getUTCDay();
            let label = "";
            if (this.state.scale === "week") {
                label = `${WEEKDAYS[wd]} ${d.getUTCDate()}`;
            } else if (this.state.scale === "month") {
                label = String(d.getUTCDate());
            } else if (wd === 1) {
                label = String(d.getUTCDate());
            }
            out.push({
                key: s,
                label,
                off: off.has(s),
                today: s === today,
                style: `left:${i * this.dayW}px;width:${this.dayW}px`,
            });
        }
        return out;
    }
    get todayStyle() {
        const t = this.state.data && this.state.data.today;
        if (!t) {
            return "";
        }
        const i = this.idx(t);
        if (i < 0 || i >= this.days) {
            return "display:none";
        }
        return `left:${this.LABEL_W + i * this.dayW + this.dayW / 2}px`;
    }

    // ---------------------------------------------------------------- bars
    bar(t) {
        const n = this.days;
        const s = this.idx(t.start);
        const e = this.idx(t.end) + 1; // exclusive
        const res = { visible: false, tail: false };
        const left = Math.max(s, 0);
        const right = Math.min(e, n);
        if (right > left) {
            res.visible = true;
            res.cutLeft = s < 0;
            res.cutRight = e > n;
            res.style = `left:${left * this.dayW + 1}px;width:${Math.max((right - left) * this.dayW - 2, 4)}px`;
            res.wide = (right - left) * this.dayW > 70;
        }
        if (t.overdue && this.state.data) {
            const ts = Math.max(e, 0);
            const te = Math.min(this.idx(this.state.data.today) + 1, n);
            if (te > ts) {
                res.tail = `left:${ts * this.dayW}px;width:${(te - ts) * this.dayW - 1}px`;
            }
        }
        if (t.deadline) {
            const d = this.idx(t.deadline);
            if (d >= 0 && d < n) {
                res.mark = `left:${(d + 1) * this.dayW - 6}px`;
            }
        }
        return res;
    }
    lateDays(t) {
        if (!t.overdue || !this.state.data) {
            return 0;
        }
        return Math.round((parse(this.state.data.today) - parse(t.deadline)) / DAY);
    }
    tooltip(t) {
        const lines = [
            `${t.number ? t.number + " " : ""}${t.name}`,
            `სტადია: ${t.stage || KINDS[t.kind] || ""}   პროგრესი: ${t.progress}%`,
            `დაწყება: ${fmt(t.start)}   ვადა: ${t.deadline ? fmt(t.deadline) : "არ არის"}`,
        ];
        if (t.overdue) {
            lines.push(`⏰ ვადაგადაცილებული: ${this.lateDays(t)} დღე`);
        }
        if (t.closed_on) {
            lines.push(`დასრულდა: ${fmt(t.closed_on)}`);
        }
        lines.push(`მთავარი პასუხისმგებელი: ${t.responsible || "-"}`);
        lines.push(`შემსრულებლები: ${t.users || "-"}`);
        lines.push(`დეპარტამენტი: ${t.department}${t.project ? "   პროექტი: " + t.project : ""}`);
        lines.push(`პრიორიტეტი: ${PRIORITY[t.priority] || "-"}`);
        return lines.join("\n");
    }

    // ---------------------------------------------------------------- data
    async load() {
        this.state.loading = true;
        const { from, to } = this.range;
        if (this.state.view !== "timeline") {
            this.state.work = await this.orm.call("project.task", "sh_workload_data", [iso(from), iso(to)], {
                mode: this.state.view,
                bucket: this.state.scale === "quarter" ? "week" : "day",
                department_id: this.state.departmentId ? Number(this.state.departmentId) : false,
                user_id: this.state.userId ? Number(this.state.userId) : false,
                subtasks: this.state.subtasks,
            });
            this.state.loading = false;
            return;
        }
        const mine = this.state.scope === "mine";
        this.state.data = await this.orm.call("project.task", "sh_timeline_data", [iso(from), iso(to)], {
            mine,
            group_by: this.state.groupBy,
            status: this.state.showDone ? "all" : "open",
            department_id: this.state.departmentId ? Number(this.state.departmentId) : false,
            user_id: !mine && this.state.userId ? Number(this.state.userId) : false,
        });
        if (mine) {
            this.state.data.department_id = false;
        }
        this.state.loading = false;
    }

    // ---------------------------------------------------------------- simple view helpers
    get isManager() {
        return Boolean(this.state.data && this.state.data.is_manager);
    }
    // "ჩემი": one flat list sorted by deadline; "ყველა": grouped
    get flatTasks() {
        const all = [];
        const seen = new Set();
        for (const g of this.state.data.groups) {
            for (const t of g.tasks) {
                if (!seen.has(t.id)) {
                    seen.add(t.id);
                    all.push(t);
                }
            }
        }
        return all.sort((a, b) => (a.overdue === b.overdue ? 0 : a.overdue ? -1 : 1) || (a.end < b.end ? -1 : a.end > b.end ? 1 : 0));
    }
    // 5 simple colours instead of every stage kind
    simpleKind(t) {
        if (t.overdue) {
            return "late";
        }
        return { new: "todo", accepted: "todo", review: "review", done: "done", cancelled: "cancel" }[t.kind] || "doing";
    }
    daysLeft(t) {
        return Math.round((parse(t.deadline) - parse(this.state.data.today)) / DAY);
    }
    dueText(t) {
        if (t.kind === "done") {
            return `✓ დასრულდა ${t.closed_on ? fmt(t.closed_on).slice(0, 5) : ""}`;
        }
        if (t.overdue) {
            const d = this.lateDays(t);
            return d > 0 ? `⏰ ${d} დღით გადაცილებული` : "⏰ ვადა გავიდა დღეს";
        }
        if (!t.deadline) {
            return "ვადა არ აქვს";
        }
        const left = this.daysLeft(t);
        if (left === 0) {
            return "ვადა: დღეს";
        }
        return `ვადა: ${fmt(t.deadline).slice(0, 5)} (კიდევ ${left} დღე)`;
    }
    dueClass(t) {
        if (t.overdue) {
            return "o_sh_due_late";
        }
        if (t.deadline && t.kind !== "done" && this.daysLeft(t) <= 1) {
            return "o_sh_due_soon";
        }
        return "";
    }
    setScope(scope) {
        this.state.scope = scope;
        this.load();
    }
    toggleDone(ev) {
        this.state.showDone = ev.target.checked;
        this.load();
    }

    // ---------------------------------------------------------------- workload: simple bars
    // one bar per person / department: overdue + due in 7 days + the rest of the open tasks
    get barRows() {
        const rows = (this.state.work ? this.state.work.rows : []).filter((r) => r.open);
        const max = Math.max(1, ...rows.map((r) => r.open));
        const team = this.state.view === "team";
        return rows
            .map((r) => {
                const late = new Set(r.overdue_ids);
                const soonIds = r.due_ids.filter((id) => !late.has(id));
                const taken = new Set([...r.overdue_ids, ...soonIds]);
                const restIds = r.open_ids.filter((id) => !taken.has(id));
                const load = team ? r.per_person : r.open;
                const status = load >= 5 ? "over" : load >= 3 ? "busy" : "ok";
                const pct = (v) => (100 * v) / max;
                return {
                    ...r,
                    soon: soonIds.length,
                    soon_ids: soonIds,
                    rest: restIds.length,
                    rest_ids: restIds,
                    wLate: pct(r.overdue),
                    wSoon: pct(soonIds.length),
                    wRest: pct(restIds.length),
                    status,
                    statusLabel: { over: "გადატვირთული", busy: "დატვირთული", ok: "ნორმა" }[status],
                };
            })
            .sort((a, b) => b.open - a.open || b.overdue - a.overdue);
    }

    // ---------------------------------------------------------------- workload
    get filterLists() {
        const src = this.state.view === "timeline" ? this.state.data : this.state.work;
        return src ? { departments: src.departments, users: src.users } : null;
    }
    get cellW() {
        return this.state.scale === "quarter" ? 64 : this.state.scale === "week" ? 70 : 34;
    }
    loadClass(cell, row) {
        const v = this.state.view === "team" ? cell.avg : cell.count;
        if (!cell.count) {
            return "o_sh_wl_zero";
        }
        for (const [max, cls] of LOAD_STEPS) {
            if (v <= max && cls) {
                return cls;
            }
        }
        return "o_sh_wl_over";
    }
    cellTitle(cell, row) {
        if (!cell.count) {
            return `${row.label}: დავალება არ არის`;
        }
        let t = `${row.label}: ${cell.count} ღია დავალება`;
        if (this.state.view === "team") {
            t += ` (${cell.avg} ერთ ადამიანზე)`;
        }
        if (cell.late) {
            t += `, მათ შორის ${cell.late} ვადაგადაცილებული`;
        }
        return t + " - დააჭირეთ სიის სანახავად";
    }
    async openIds(ids, title) {
        if (!ids || !ids.length) {
            return;
        }
        const action = await this.orm.call("project.task", "sh_tasks_action", [ids, title]);
        this.action.doAction(action);
    }
    setView(view) {
        this.state.view = view;
        this.load();
    }

    // ---------------------------------------------------------------- actions
    setScale(scale) {
        this.state.scale = scale;
        this.load();
    }
    move(step) {
        const a = this.state.anchor;
        if (this.state.scale === "week") {
            this.state.anchor = addDays(a, 7 * step);
        } else {
            const months = this.state.scale === "quarter" ? 3 : 1;
            this.state.anchor = new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() + months * step, 1));
        }
        this.load();
    }
    goToday() {
        this.state.anchor = this.today();
        this.load();
    }
    setFilter(key, ev) {
        this.state[key] = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        this.load();
    }
    onSearchKey(ev) {
        if (ev.key === "Enter") {
            this.state.search = ev.target.value;
            this.load();
        }
    }
    toggle(key) {
        this.state.expanded[key] = !this.state.expanded[key];
    }
    expandAll(open) {
        for (const g of this.state.data.groups) {
            this.state.expanded[g.key] = open;
        }
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
}

registry.category("actions").add("sh_task_timeline", TaskTimeline);
