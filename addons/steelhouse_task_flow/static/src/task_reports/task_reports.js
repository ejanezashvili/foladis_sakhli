import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MONTHS = ["იანვარი", "თებერვალი", "მარტი", "აპრილი", "მაისი", "ივნისი", "ივლისი",
    "აგვისტო", "სექტემბერი", "ოქტომბერი", "ნოემბერი", "დეკემბერი"];
const SCALES = { month: "თვე", quarter: "3 თვე", year: "წელი" };
const VIEWS = [
    { key: "deadline", label: "ვადების დაცვა", icon: "fa-calendar-check-o", method: "sh_deadline_data" },
    { key: "stops", label: "შეჩერება და გაუქმება", icon: "fa-pause-circle-o", method: "sh_stops_data" },
];
const GROUPS = { department: "დეპარტამენტი", project: "პროექტი", user: "თანამშრომელი" };
const TREND_H = 110; // px, the tallest month

const iso = (d) => d.toISOString().slice(0, 10);

// "რეპორტინგი": deadline compliance and holds / cancellations (models/task_reports.py).
// Employees see their own tasks; heads and admins also "ყველა".
export class TaskReports extends Component {
    static template = "steelhouse_task_flow.TaskReports";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.VIEWS = VIEWS;
        this.SCALES = SCALES;
        this.scaleKeys = Object.keys(SCALES);
        this.GROUPS = GROUPS;
        this.groupKeys = Object.keys(GROUPS);
        const params = (this.props.action && this.props.action.params) || {};
        const n = new Date();
        this.state = useState({
            view: params.view === "stops" ? "stops" : "deadline",
            scope: null, // decided by the first answer: heads start on "ყველა"
            scale: "month",
            anchor: new Date(Date.UTC(n.getFullYear(), n.getMonth(), 1)),
            group: "department",
            departmentId: "",
            userId: "",
            data: null,
            dataView: null,
            open: {},
            loading: true,
        });
        onWillStart(() => this.load());
    }

    // ---------------------------------------------------------------- period
    get range() {
        const y = this.state.anchor.getUTCFullYear();
        const m = this.state.anchor.getUTCMonth();
        if (this.state.scale === "year") {
            return { from: new Date(Date.UTC(y, 0, 1)), to: new Date(Date.UTC(y, 12, 0)) };
        }
        if (this.state.scale === "quarter") {
            const q = m - (m % 3);
            return { from: new Date(Date.UTC(y, q, 1)), to: new Date(Date.UTC(y, q + 3, 0)) };
        }
        return { from: new Date(Date.UTC(y, m, 1)), to: new Date(Date.UTC(y, m + 1, 0)) };
    }
    get periodLabel() {
        const { from, to } = this.range;
        if (this.state.scale === "year") {
            return `${from.getUTCFullYear()} წელი`;
        }
        if (this.state.scale === "quarter") {
            return `${MONTHS[from.getUTCMonth()]} - ${MONTHS[to.getUTCMonth()]} ${to.getUTCFullYear()}`;
        }
        return `${MONTHS[from.getUTCMonth()]} ${from.getUTCFullYear()}`;
    }
    move(step) {
        const a = this.state.anchor;
        const months = { month: 1, quarter: 3, year: 12 }[this.state.scale] * step;
        this.state.anchor = new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() + months, 1));
        this.load();
    }
    goToday() {
        const n = new Date();
        this.state.anchor = new Date(Date.UTC(n.getFullYear(), n.getMonth(), 1));
        this.load();
    }
    setScale(scale) {
        this.state.scale = scale;
        this.load();
    }

    // ---------------------------------------------------------------- data
    async load() {
        this.state.loading = true;
        const view = this.state.view;
        const mine = this.state.scope === "mine";
        const { from, to } = this.range;
        const method = VIEWS.find((v) => v.key === view).method;
        const data = await this.orm.call("project.task", method, [iso(from), iso(to)], {
            mine,
            group_by: this.state.group,
            department_id: !mine && this.state.departmentId ? Number(this.state.departmentId) : false,
            user_id: !mine && this.state.userId ? Number(this.state.userId) : false,
        });
        if (this.state.scope === null) {
            this.state.scope = data.is_manager ? "all" : "mine";
        }
        this.state.data = data;
        this.state.dataView = view;
        this.state.loading = false;
    }
    get d() {
        return this.state.dataView === this.state.view ? this.state.data : null;
    }
    get isManager() {
        return Boolean(this.state.data && this.state.data.is_manager);
    }
    get groupLabel() {
        return GROUPS[this.state.group];
    }
    get cols() {
        return (this.state.view === "deadline" ? 7 : 6) + (this.state.group === "project" ? 1 : 0);
    }
    setView(view) {
        this.state.view = view;
        this.state.open = {};
        this.load();
    }
    setScope(scope) {
        this.state.scope = scope;
        this.load();
    }
    setGroup(group) {
        this.state.group = group;
        this.state.open = {};
        this.load();
    }
    setFilter(key, ev) {
        this.state[key] = ev.target.value;
        this.load();
    }
    toggle(key) {
        this.state.open[key] = !this.state.open[key];
    }

    // ---------------------------------------------------------------- deadline: monthly trend
    get trendBars() {
        const trend = this.d.trend;
        const max = Math.max(1, ...trend.map((m) => m.ontime + m.late));
        const h = (v) => (v ? Math.max(Math.round((TREND_H * v) / max), 18) : 0);
        return trend.map((m) => ({
            ...m,
            hOn: h(m.ontime),
            hLate: h(m.late),
            pctLabel: m.pct === null ? "-" : m.pct + "%",
            level: m.pct === null ? "" : m.pct >= 85 ? "good" : m.pct >= 60 ? "mid" : "bad",
        }));
    }
    pctLabel(r) {
        return r.pct === null ? "-" : r.pct + "%";
    }

    // ---------------------------------------------------------------- open tasks
    async openIds(ids, title) {
        if (!ids || !ids.length) {
            return;
        }
        const action = await this.orm.call("project.task", "sh_tasks_action", [ids, title]);
        this.action.doAction(action);
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

    // ---------------------------------------------------------------- Excel (CSV)
    download(name, lines) {
        const line = (a) => a.map((v) => '"' + (v === null || v === undefined ? "" : v + "").replace(/"/g, '""') + '"').join(",");
        const blob = new Blob(["﻿" + lines.map(line).join("\r\n")], { type: "text/csv;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `${name} ${iso(this.range.from)} - ${iso(this.range.to)}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
    }
    exportDeadline() {
        const d = this.d;
        const out = [[this.groupLabel, "დავალება", "ვადა ეწურებოდა", "დროულად", "დაგვიანებით ან ჩაუბარებელი", "დროულად %", "საშუალო დაგვიანება",
            "ყველაზე დიდი დაგვიანება", "ვადა ჯერ არ მოსულა", "ახლა ვადაგადაცილებული", "შემსრულებლები"]];
        const row = (r) => [r.label, "", r.done, r.ontime, r.late, this.pctLabel(r), r.avg_late, r.max_late, r.nodl, r.overdue, ""];
        for (const r of d.rows) {
            out.push(row(r));
            for (const it of r.items) {
                out.push([r.label, it.label, "", "", it.kind === "late" ? it.amount : "", "", "", "", "",
                    it.kind === "overdue" ? it.amount : "", it.who]);
            }
        }
        out.push(row(d.total));
        out.push([]);
        out.push(["თვე", "", "", "დროულად", "დაგვიანებით", "დროულად %"]);
        for (const m of d.trend) {
            out.push([m.label, "", "", m.ontime, m.late, m.pct === null ? "-" : m.pct + "%"]);
        }
        this.download("ვადების დაცვა", out);
    }
    exportStops() {
        const d = this.d;
        const out = [[this.groupLabel, "დავალება", "შეჩერება", "საშუალო ხანგრძლივობა", "ყველაზე გრძელი", "ახლა შეჩერებული",
            "გაუქმებული", "მიზეზი", "თარიღი"]];
        const row = (r) => [r.label, "", r.holds, r.avg, r.max, r.now, r.cancels, "", ""];
        for (const r of d.rows) {
            out.push(row(r));
            for (const it of r.items) {
                out.push([r.label, it.label, it.kind === "cancel" ? "" : it.amount, "", "", it.kind === "now" ? "დიახ" : "",
                    it.kind === "cancel" ? "დიახ" : "", it.reason, it.date]);
            }
        }
        out.push(row(d.total));
        out.push([]);
        out.push(["შეჩერების მიზეზი", "", "რამდენჯერ", "საშუალო ხანგრძლივობა"]);
        for (const r of d.hold_reasons) {
            out.push([r.reason, "", r.count, r.avg]);
        }
        out.push([]);
        out.push(["გაუქმების მიზეზი", "", "რამდენჯერ"]);
        for (const r of d.cancel_reasons) {
            out.push([r.reason, "", r.count]);
        }
        this.download("შეჩერება და გაუქმება", out);
    }
}

registry.category("actions").add("sh_task_reports", TaskReports);
