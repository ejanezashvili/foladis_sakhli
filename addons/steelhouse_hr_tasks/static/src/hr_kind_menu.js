/** @odoo-module **/
// „კადრები“: a template saved (its own form or the settings) -> the top menu is loaded again, so its item in
// „ახალი მოთხოვნა“ shows (or hides) at once, without F5; the cached form views are dropped too, so the tab line
// of the settings shows the new template. Only these two forms, nothing else changes.
import { patch } from "@web/core/utils/patch";
import { rpcBus } from "@web/core/network/rpc";
import { FormController } from "@web/views/form/form_controller";

const SH_HR_MENU_MODELS = ["steelhouse.hr.kind", "steelhouse.hr.task.config"];

patch(FormController.prototype, {
    async onRecordSaved(record, changes) {
        const result = await super.onRecordSaved(...arguments);
        if (SH_HR_MENU_MODELS.includes(this.props.resModel) && this.env.services.menu) {
            if (this.props.resModel === "steelhouse.hr.kind") {
                rpcBus.trigger("CLEAR-CACHES", "get_views");
            }
            await this.env.services.menu.reload();
        }
        return result;
    },
});
