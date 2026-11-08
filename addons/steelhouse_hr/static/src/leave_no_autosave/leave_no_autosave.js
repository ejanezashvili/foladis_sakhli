import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

// Time off requests are saved only with the Save button: closing/reloading the page,
// switching the browser tab or leaving the form drops unsaved changes
// (Odoo saves them automatically by default).
const NO_AUTOSAVE_MODELS = ["hr.leave"];

patch(FormController.prototype, {
    get shNoAutosave() {
        return NO_AUTOSAVE_MODELS.includes(this.props.resModel);
    },

    beforeVisibilityChange() {
        if (this.shNoAutosave) {
            return;
        }
        return super.beforeVisibilityChange(...arguments);
    },

    async beforeLeave(options) {
        if (this.shNoAutosave) {
            if (this.model.root.dirty) {
                await this.model.root.discard();
            }
            return;
        }
        return super.beforeLeave(...arguments);
    },

    async beforeUnload(ev) {
        if (this.shNoAutosave) {
            return;
        }
        return super.beforeUnload(...arguments);
    },
});
