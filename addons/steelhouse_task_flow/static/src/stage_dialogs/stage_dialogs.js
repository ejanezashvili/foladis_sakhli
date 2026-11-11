import { patch } from "@web/core/utils/patch";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

// Task form, stage bar: moving to a stage that needs input opens its dialog directly
// (no intermediate warning, no pending unsaved stage that would ask again).
const DIALOGS = {
    on_hold: "steelhouse_task_flow.action_sh_task_hold_wizard",
    returned: "steelhouse_task_flow.action_sh_task_return_wizard",
    cancelled: "steelhouse_task_flow.action_sh_task_cancel_wizard",
    done: "steelhouse_task_flow.action_sh_task_final_wizard",
};

patch(StatusBarField.prototype, {
    async selectItem(item) {
        const { name, record } = this.props;
        if (record.resModel === "project.task" && name === "stage_id" && record.resId && item?.value) {
            const [stage] = await this.env.services.orm.read("project.task.type", [item.value], ["sh_kind"]);
            const kind = stage?.sh_kind;
            if (DIALOGS[kind] && record.data.sh_kind !== kind) {
                if (record.isDirty) {
                    await record.save();
                }
                const context =
                    kind === "done"
                        ? { default_task_id: record.resId, default_note: record.data.sh_final_note || false }
                        : { default_task_id: record.resId, default_mode: kind };
                return this.env.services.action.doAction(DIALOGS[kind], {
                    additionalContext: context,
                    onClose: () => record.load(),
                });
            }
        }
        return super.selectItem(...arguments);
    },
});
