import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

// "საერთო ჩატი" on the task form: opens the task's group chat as a chat window (pop-up),
// the page stays where it is.
export class TaskChatButton extends Component {
    static template = "steelhouse_task_flow.TaskChatButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.store = useService("mail.store");
        this.notification = useService("notification");
    }

    async onClick() {
        const record = this.props.record;
        if (record.isNew || (await record.isDirty())) {
            if (!(await record.save())) {
                return;
            }
        }
        const id = await this.orm.call("project.task", "sh_chat_channel_id", [[record.resId]]);
        const thread = id && (await this.store.Thread.getOrFetch({ model: "discuss.channel", id }));
        if (!thread) {
            this.notification.add("ჩატის გახსნა ვერ მოხერხდა.", { type: "danger" });
            return;
        }
        thread.open({ focus: true, bypassCompact: true });
    }
}

registry.category("view_widgets").add("sh_task_chat_button", { component: TaskChatButton });
