import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const SHOW = 6;

// Task card: "☑ ქვედავალებები x/y" and "⛓ თანმიმდევრობა x/y" - the list opens inside the card
// (one at a time); a name opens that task. Read only.
export class TaskCardLists extends Component {
    static template = "steelhouse_task_flow.TaskCardLists";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ open: false, items: [], loading: false });
        this.SHOW = SHOW;
    }

    get data() {
        return this.props.record.data;
    }
    get subTotal() {
        return this.data.subtask_count || 0;
    }
    get subDone() {
        return this.data.closed_subtask_count || 0;
    }
    get stepTotal() {
        return this.data.sh_step_total || 0;
    }
    get stepDone() {
        return this.data.sh_step_done || 0;
    }

    async toggle(kind) {
        if (this.state.open === kind) {
            this.state.open = false;
            return;
        }
        this.state.open = kind;
        this.state.loading = true;
        this.state.items = await this.orm.call("project.task", "sh_card_list", [[this.props.record.resId], kind]);
        this.state.loading = false;
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

registry.category("view_widgets").add("sh_card_lists", {
    component: TaskCardLists,
    fieldDependencies: [
        { name: "subtask_count", type: "integer" },
        { name: "closed_subtask_count", type: "integer" },
        { name: "sh_step_total", type: "integer" },
        { name: "sh_step_done", type: "integer" },
    ],
});
