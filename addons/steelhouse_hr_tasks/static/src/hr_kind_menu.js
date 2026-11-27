/** @odoo-module **/
// „კადრები“: a template saved (its own form or the settings) -> the top menu is loaded again, so its item in
// „ახალი მოთხოვნა“ shows (or hides) at once, without F5; the cached form views are dropped too, so the tab line
// of the settings shows the new template. A template deleted from its form -> the same, and back to the settings
// (Odoo would open an empty new template). Only these two forms, nothing else changes.
import { patch } from "@web/core/utils/patch";
import { rpcBus } from "@web/core/network/rpc";
import { FormController } from "@web/views/form/form_controller";

const SH_HR_KIND = "steelhouse.hr.kind";
const SH_HR_MENU_MODELS = [SH_HR_KIND, "steelhouse.hr.task.config"];

async function shHrRefresh(env, dropViews) {
    if (dropViews) {
        rpcBus.trigger("CLEAR-CACHES", "get_views");
    }
    if (env.services.menu) {
        await env.services.menu.reload();
    }
}

patch(FormController.prototype, {
    async onRecordSaved(record, changes) {
        const result = await super.onRecordSaved(...arguments);
        if (SH_HR_MENU_MODELS.includes(this.props.resModel)) {
            await shHrRefresh(this.env, this.props.resModel === SH_HR_KIND);
        }
        return result;
    },
    get deleteConfirmationDialogProps() {
        const props = super.deleteConfirmationDialogProps;
        if (this.props.resModel !== SH_HR_KIND) {
            return props;
        }
        return {
            ...props,
            confirm: async () => {
                await this.model.root.delete();
                await shHrRefresh(this.env, true);
                await this.env.services.action.doAction("steelhouse_hr_tasks.action_sh_hr_task_config", {
                    clearBreadcrumbs: true,
                });
            },
        };
    },
});
