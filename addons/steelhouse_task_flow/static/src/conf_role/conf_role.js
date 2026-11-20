import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";

// Employees app, "კონფიდენციალური": "+" card after the last member; one click in the list adds a person
export class ConfAddDialog extends Component {
    static template = "steelhouse_task_flow.ConfAddDialog";
    static components = { Dialog };
    static props = { close: Function, onAdded: Function };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ term: "", items: [], busy: false });
        onWillStart(() => this.search());
    }
    async search() {
        this.state.items = await this.orm.call("hr.employee.public", "sh_conf_candidates", [this.state.term]);
    }
    onInput(ev) {
        this.state.term = ev.target.value;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.search(), 250);
    }
    avatar(item) {
        return `/web/image/hr.employee.public/${item.id}/avatar_128`;
    }
    async add(item) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("hr.employee.public", "sh_conf_add", [[item.id]]);
            await this.props.onAdded(item);
            this.props.close();
        } finally {
            this.state.busy = false;
        }
    }
}

export class ConfKanbanRenderer extends KanbanRenderer {
    static template = "steelhouse_task_flow.ConfKanbanRenderer";

    setup() {
        super.setup();
        this.dialogs = useService("dialog");
        this.notification = useService("notification");
    }
    openAdd() {
        this.dialogs.add(ConfAddDialog, {
            onAdded: async (item) => {
                await this.props.list.model.load();
                this.notification.add(`${item.name} დაემატა კონფიდენციალურს`, { type: "success" });
            },
        });
    }
}

registry.category("views").add("sh_conf_kanban", { ...kanbanView, Renderer: ConfKanbanRenderer });
