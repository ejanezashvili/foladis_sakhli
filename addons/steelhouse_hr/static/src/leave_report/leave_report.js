import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

// "შვებულება → რეპორტინგი → შვებულების რეპორტი" (models/leave_report.py)
export class LeaveReport extends Component {
    static template = "steelhouse_hr.LeaveReport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        const year = new Date().getFullYear();
        this.state = useState({
            lists: { departments: [], employees: [], states: [], views: [] },
            params: {
                date_from: `${year}-01-01`,
                date_to: `${year}-12-31`,
                department_id: 0,
                employee_id: 0,
                states: ["validate"],
                view: "month",
                group: "employee",
            },
            data: null,
            open: {},
            loading: false,
            busy: "",
        });
        onWillStart(async () => {
            this.state.lists = await this.orm.call("sh.leave.report", "sh_lists", []);
            await this.load();
        });
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("sh.leave.report", "sh_report_data", [this.state.params]);
            this.state.open = {};
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------ filters
    setParam(key, value) {
        this.state.params[key] = value;
        if (key === "department_id") {
            this.state.params.employee_id = 0;
        }
        this.load();
    }
    onDate(key, ev) {
        if (ev.target.value) {
            this.setParam(key, ev.target.value);
        }
    }
    onSelect(key, ev) {
        this.setParam(key, parseInt(ev.target.value) || 0);
    }
    toggleState(key) {
        const states = this.state.params.states;
        const next = states.includes(key) ? states.filter((s) => s !== key) : [...states, key];
        if (next.length) {
            this.setParam("states", next);
        }
    }
    quick(kind) {
        const now = new Date();
        let from, to;
        if (kind === "today") {
            from = to = now;
        } else if (kind === "month") {
            from = new Date(now.getFullYear(), now.getMonth(), 1);
            to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        } else if (kind === "quarter") {
            const q = Math.floor(now.getMonth() / 3) * 3;
            from = new Date(now.getFullYear(), q, 1);
            to = new Date(now.getFullYear(), q + 3, 0);
        } else if (kind === "last_year") {
            from = new Date(now.getFullYear() - 1, 0, 1);
            to = new Date(now.getFullYear() - 1, 11, 31);
        } else {
            from = new Date(now.getFullYear(), 0, 1);
            to = new Date(now.getFullYear(), 11, 31);
        }
        this.state.params.date_from = iso(from);
        this.state.params.date_to = iso(to);
        this.load();
    }
    get employees() {
        const dept = this.state.params.department_id;
        const all = this.state.lists.employees;
        return dept ? all.filter((e) => e.department_id === dept) : all;
    }

    // ------------------------------------------------------------------ table
    num(value) {
        if (!value) {
            return "";
        }
        return String(Math.round(value * 100) / 100).replace(".", ",");
    }
    toggle(key) {
        this.state.open[key] = !this.state.open[key];
    }
    openLeave(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.leave",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ------------------------------------------------------------------ exports
    async exportExcel() {
        this.state.busy = "excel";
        try {
            this.action.doAction(await this.orm.call("sh.leave.report", "sh_report_excel", [this.state.params]));
        } finally {
            this.state.busy = "";
        }
    }
    async exportPdf() {
        this.state.busy = "pdf";
        try {
            await this.action.doAction(await this.orm.call("sh.leave.report", "sh_report_pdf", [this.state.params]));
        } finally {
            this.state.busy = "";
        }
    }
}

registry.category("actions").add("sh_leave_report", LeaveReport);
