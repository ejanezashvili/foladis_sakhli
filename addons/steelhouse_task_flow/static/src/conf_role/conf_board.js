import { onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { kanbanView } from "@web/views/kanban/kanban_view";

// "🔒 კონფიდენციალური" board: the numbers on top (models/task_conf_board.py sh_conf_summary)
export class ConfBoardRenderer extends KanbanRenderer {
    static template = "steelhouse_task_flow.ConfBoardRenderer";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.summary = useState({ total: 0, new: 0, wip: 0, review: 0, overdue: 0 });
        onWillStart(() => this.loadSummary(this.props));
        onWillUpdateProps((next) => this.loadSummary(next));
    }
    async loadSummary(props) {
        const data = await this.orm.call("project.task", "sh_conf_summary", [props.list.domain]);
        Object.assign(this.summary, data);
    }
}

registry.category("views").add("sh_conf_board", { ...kanbanView, Renderer: ConfBoardRenderer });
