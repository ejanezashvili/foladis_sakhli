import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { downloadTablePdf } from "@steelhouse_task_flow/sh_pdf/sh_pdf";

const DAY = 86400000;
const LABEL_W = 320;
const MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი", "ივლისი",
    "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
const WEEKDAYS = ["კვ", "ორ", "სამ", "ოთხ", "ხუთ", "პარ", "შაბ"];
const SCALES = {
    day7: { label: "კვირა", dayW: 150 }, // the home page ("ჩემი") only
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
    { key: "worktime", label: "სამუშაო დრო", icon: "fa-clock-o" },
    { key: "returns", label: "დაბრუნებები", icon: "fa-undo" },
];
// home page ("მთავარი" - "ჩემი"): which statuses to show, open ones by default
export const MY_KINDS = ["new", "accepted", "in_progress", "on_hold", "review", "returned", "done", "cancelled"];
const MY_KINDS_DEFAULT = ["new", "accepted", "in_progress", "on_hold", "review", "returned"];
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
        // embedded on the home page ("ჩემი"): my tasks only, this week by default, statuses to pick
        this.embedded = Boolean(this.props.embedded);
        this.LABEL_W = window.innerWidth < 768 ? 170 : this.embedded ? 280 : LABEL_W;
        this.SCALES = SCALES;
        this.scaleKeys = Object.keys(SCALES).filter((k) => this.embedded || k !== "day7");
        this.MY_KINDS = MY_KINDS;
        this.KINDS = KINDS;
        this.VIEWS = VIEWS;
        this.state = useState({
            view: "timeline",
            scope: "mine",
            detail: false,
            showDone: false,
            work: null,
            wt: null,
            wtOpen: {},
            ret: null,
            retGroup: "project",
            scale: this.embedded ? "day7" : "month",
            kinds: [...MY_KINDS_DEFAULT],
            myGroup: true, // home page: grouped by project / department (open), or one list
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
        if (this.state.scale === "week" || this.state.scale === "day7") {
            const from = addDays(a, -((a.getUTCDay() + 6) % 7)); // Monday
            return { from, to: addDays(from, this.state.scale === "day7" ? 6 : 13) };
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
            if (this.state.scale === "week" || this.state.scale === "day7") {
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
    // "17.11": a bar cut at the period start shows when the task really started
    dayMonth(s) {
        return s ? `${s.slice(8, 10)}.${s.slice(5, 7)}` : "";
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
        if (this.state.view === "returns") {
            const mine = this.state.scope === "mine";
            this.state.ret = await this.orm.call("project.task", "sh_returns_data", [iso(from), iso(to)], {
                mine,
                group_by: this.state.retGroup,
                department_id: !mine && this.state.departmentId ? Number(this.state.departmentId) : false,
                user_id: !mine && this.state.userId ? Number(this.state.userId) : false,
            });
            this.state.loading = false;
            return;
        }
        if (this.state.view === "worktime") {
            const mine = this.state.scope === "mine";
            this.state.wt = await this.orm.call("project.task", "sh_worktime_data", [iso(from), iso(to)], {
                mine,
                department_id: !mine && this.state.departmentId ? Number(this.state.departmentId) : false,
                user_id: !mine && this.state.userId ? Number(this.state.userId) : false,
            });
            this.state.loading = false;
            return;
        }
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
            status: this.embedded || this.state.showDone ? "all" : "open",
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
        return Boolean((this.state.data && this.state.data.is_manager) || (this.state.wt && this.state.wt.is_manager)
            || (this.state.ret && this.state.ret.is_manager));
    }
    // employees see Timeline + "სამუშაო დრო"; heads see all tabs
    get tabs() {
        return this.isManager ? VIEWS : VIEWS.filter((v) => ["timeline", "worktime", "returns"].includes(v.key));
    }
    setRetGroup(g) {
        this.state.retGroup = g;
        this.state.wtOpen = {};
        this.load();
    }
    get retGroupLabel() {
        return { project: "პროექტი", department: "დეპარტამენტი", user: "თანამშრომელი" }[this.state.retGroup];
    }
    exportRet(pdf = false) {
        const r = this.state.ret;
        const out = [[this.retGroupLabel, "დავალება", "შემოწმებაზე", "დაბრუნებული დავალება", "დაბრუნება სულ", "დაბრუნების %", "ახლა ხელახლა კეთდება"]];
        for (const row of r.rows) {
            out.push([row.label, "", row.reviewed, row.returned, row.returns, row.pct + "%", row.rework]);
            for (const it of row.items) {
                out.push([row.label, it.label, "", "", it.returns, "", it.stage]);
            }
        }
        out.push(["სულ", "", r.total.reviewed, r.total.returned, r.total.returns, r.total.pct + "%", r.total.rework]);
        this.outputTable("დაბრუნებები", out, pdf);
    }
    // Excel (CSV) or PDF of the same rows
    outputTable(name, rows, pdf) {
        if (pdf) {
            const who = this.state.scope === "mine" ? "ჩემი დავალებები" : "ყველა";
            return downloadTablePdf(this.orm, this.action, name, `${this.periodLabel} · ${who}`, rows);
        }
        const line = (a) => a.map((v) => '"' + String(v === null || v === undefined ? "" : v).replace(/"/g, '""') + '"').join(",");
        const blob = new Blob(["\ufeff" + rows.map(line).join("\r\n")], { type: "text/csv;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${name} ${iso(this.range.from)} - ${iso(this.range.to)}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
    }
    toggleWt(key) {
        this.state.wtOpen[key] = !this.state.wtOpen[key];
    }
    // Excel: the table as a CSV file (opens in Excel)
    exportWt(pdf = false) {
        const wt = this.state.wt;
        const out = [["დეპარტამენტი", "თანამშრომელი", "დავალება", "საშუალო სამუშაო დრო", "ყველაზე სწრაფი", "ყველაზე გრძელი", "ახლა მიმდინარე"]];
        for (const r of wt.rows) {
            out.push([r.label, "", r.count, r.avg_str, r.min_str, r.max_str, r.running]);
            for (const u of r.users) {
                out.push([r.label, u.label, u.count, u.avg_str, u.min_str, u.max_str, u.running]);
            }
        }
        out.push(["სულ", "", wt.total.count, wt.total.avg_str, wt.total.min_str, wt.total.max_str, wt.total.running]);
        this.outputTable("სამუშაო დრო", out, pdf);
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
        const kinds = this.embedded && new Set(this.state.kinds);
        return all.filter((t) => !kinds || kinds.has(t.kind)).sort((a, b) => (a.overdue === b.overdue ? 0 : a.overdue ? -1 : 1) || (a.end < b.end ? -1 : a.end > b.end ? 1 : 0));
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
    // home page: my tasks grouped by project (else department), groups open by default
    get myGroups() {
        const groups = new Map();
        for (const t of this.flatTasks) {
            const key = t.project ? `p_${t.project}` : `d_${t.department}`;
            if (!groups.has(key)) {
                groups.set(key, { key, label: t.project || t.department, isDept: !t.project, tasks: [], overdue: 0 });
            }
            const g = groups.get(key);
            g.tasks.push(t);
            g.overdue += t.overdue ? 1 : 0;
        }
        return [...groups.values()].sort((a, b) => b.overdue - a.overdue || a.label.localeCompare(b.label));
    }
    isOpen(key) {
        return this.embedded ? this.state.expanded[key] !== false : Boolean(this.state.expanded[key]);
    }
    get allKinds() {
        return MY_KINDS.every((k) => this.state.kinds.includes(k));
    }
    // "ყველა": every status on, or (when all are on already) every status off
    toggleAllKinds() {
        this.state.kinds = this.allKinds ? [] : [...MY_KINDS];
    }
    toggleKind(kind) {
        const kinds = this.state.kinds;
        this.state.kinds = kinds.includes(kind) ? kinds.filter((k) => k !== kind) : [...kinds, kind];
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
        const src = this.state.view === "timeline" ? this.state.data : this.state.view === "worktime" ? this.state.wt : this.state.view === "returns" ? this.state.ret : this.state.work;
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
        if (this.state.scale === "week" || this.state.scale === "day7") {
            this.state.anchor = addDays(a, (this.state.scale === "day7" ? 7 : 14) * step);
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
        this.state.expanded[key] = !this.isOpen(key);
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
