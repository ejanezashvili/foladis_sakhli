import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const KIND_LABEL = {
    new: "ახალი",
    accepted: "მიღებული",
    in_progress: "მიმდინარე",
    on_hold: "შეჩერებული",
    review: "შემოწმებაზე",
    returned: "დაბრუნებული",
    done: "დასრულებული",
    cancelled: "გაუქმებული",
    late: "ვადაგადაცილებული",
};
const CHART_W = 320;
const CHART_H = 130;

// "მთავარი": personal dashboard of the current user's tasks
export class TaskDashboard extends Component {
    static template = "steelhouse_task_flow.TaskDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.KIND_LABEL = KIND_LABEL;
        this.CHART_W = CHART_W;
        this.CHART_H = CHART_H;
        // managers: "კომპანია" / "ჩემი" tabs (the last one opened is remembered)
        let tab = "company";
        try {
            tab = window.localStorage.getItem("sh_db_tab") || "company";
        } catch {
            tab = "company";
        }
        this.state = useState({ d: null, cw: null, tab, cwAllDepts: false, cwLeave: { now: false, next: false } });
        onWillStart(() => this.load());
    }

    setTab(tab) {
        this.state.tab = tab;
        try {
            window.localStorage.setItem("sh_db_tab", tab);
        } catch {
            // private window: only for this visit
        }
    }
    toggleLeave(key) {
        const list = this.state.cw && this.state.cw[key === "now" ? "away_now" : "away_next"];
        if (list && list.length) {
            this.state.cwLeave[key] = !this.state.cwLeave[key];
        }
    }
    get cwDepts() {
        const rows = (this.state.cw && this.state.cw.departments) || [];
        return this.state.cwAllDepts ? rows : rows.slice(0, 8);
    }
    get cwMaxOpen() {
        return Math.max(1, ...((this.state.cw && this.state.cw.departments) || []).map((d) => d.open));
    }
    get cwMaxDue() {
        return Math.max(1, ...((this.state.cw && this.state.cw.due_rows) || []).map((r) => r.count));
    }
    barPct(value, max) {
        return value ? Math.max(4, Math.round((100 * value) / max)) : 0;
    }

    async load() {
        const [d, cw] = await Promise.all([
            this.orm.call("project.task", "sh_dashboard_data", []),
            this.orm.call("project.task", "sh_company_week_data", [0]),
        ]);
        this.state.d = d;
        this.state.cw = cw;
    }

    // ------------------------------------------------------------ "კომპანიის კვირა" (administrators)
    async setWeek(offset) {
        this.state.cw = await this.orm.call("project.task", "sh_company_week_data", [offset]);
    }
    arrow(trend, goodWhenUp = true) {
        if (!trend) {
            return { icon: "", cls: "" };
        }
        const good = goodWhenUp ? trend > 0 : trend < 0;
        return { icon: trend > 0 ? "▲" : "▼", cls: good ? "o_sh_cw_up" : "o_sh_cw_down" };
    }
    pctText(p) {
        return p === null || p === undefined ? "-" : `${p}%`;
    }

    // ------------------------------------------------------------ weekly chart (SVG)
    get chart() {
        const week = this.state.d.week;
        const max = Math.max(1, ...week.map((w) => Math.max(w.new, w.done)));
        const step = CHART_W / (week.length - 1);
        const pt = (v, i) => [Math.round(i * step), Math.round(CHART_H - 12 - (v / max) * (CHART_H - 30))];
        const path = (key) => {
            const pts = week.map((w, i) => pt(w[key], i));
            let d = `M ${pts[0][0]} ${pts[0][1]}`;
            for (let i = 1; i < pts.length; i++) {
                const [x0, y0] = pts[i - 1];
                const [x1, y1] = pts[i];
                const cx = (x0 + x1) / 2;
                d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
            }
            return { line: d, area: `${d} L ${CHART_W} ${CHART_H} L 0 ${CHART_H} Z` };
        };
        const todayIdx = week.findIndex((w) => w.today);
        const t = todayIdx >= 0 ? pt(week[todayIdx].done, todayIdx) : null;
        return {
            done: path("done"),
            new: path("new"),
            todayX: todayIdx >= 0 ? todayIdx * step : -10,
            badge: t && { x: t[0], y: t[1], value: week[todayIdx].done },
            totalNew: week.reduce((a, w) => a + w.new, 0),
            totalDone: week.reduce((a, w) => a + w.done, 0),
        };
    }

    // ------------------------------------------------------------ rings
    ring(pct, r) {
        const c = 2 * Math.PI * r;
        const p = Math.max(0, Math.min(100, pct || 0));
        return { c, dash: `${(c * p) / 100} ${c}` };
    }
    projectPct(p) {
        return p.total ? Math.round((100 * p.done) / p.total) : 0;
    }

    // ------------------------------------------------------------ texts
    dueText(t) {
        if (t.done) {
            return "✓ დასრულებული";
        }
        if (t.kind === "late") {
            return t.days_left !== null && t.days_left < 0 ? `⏰ ${-t.days_left} დღით გადაცილებული` : "⏰ ვადა გავიდა";
        }
        if (!t.deadline) {
            return "ვადა არ აქვს";
        }
        if (t.days_left === 0) {
            return "ვადა: დღეს";
        }
        const d = t.deadline.slice(8, 10) + "." + t.deadline.slice(5, 7);
        return t.days_left === 1 ? `ვადა: ხვალ (${d})` : `ვადა: ${d} (კიდევ ${t.days_left} დღე)`;
    }
    statusText(p) {
        return { completed: "დასრულებული", late: "აქვს გადაცილება", in_progress: "მიმდინარე" }[p.status];
    }

    // ------------------------------------------------------------ actions
    openTask(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    async openIds(ids, title) {
        if (ids && ids.length) {
            this.action.doAction(await this.orm.call("project.task", "sh_tasks_action", [ids, title]));
        }
    }
    newTask() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            views: [[false, "form"]],
            target: "current",
            context: { default_user_ids: [user.userId] },
        });
    }
    openMyTasks() {
        this.action.doAction("project.action_view_my_task");
    }
    openTimeline() {
        this.action.doAction("steelhouse_task_flow.action_sh_task_timeline");
    }
}

registry.category("actions").add("sh_task_dashboard", TaskDashboard);
