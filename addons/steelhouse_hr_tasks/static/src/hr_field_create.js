/** @odoo-module **/
// „კადრები“ settings, the required-fields tags: always offer „+ ახალი ველი“ above „მეტის ძიება...“
// (Odoo shows its „შექმნა“ only after something is typed). Only for the process fields, nothing else changes.
import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

const SH_HR_FIELD = "steelhouse.hr.field";

patch(Many2XAutocomplete.prototype, {
    addCreateEditSuggestion(params) {
        if (this.props.resModel === SH_HR_FIELD) {
            return !!(this.activeActions.createEdit ?? this.activeActions.create);
        }
        return super.addCreateEditSuggestion(params);
    },
    buildCreateEditSuggestion(request) {
        const suggestion = super.buildCreateEditSuggestion(request);
        if (this.props.resModel === SH_HR_FIELD) {
            suggestion.label = "+ ახალი ველი";
        }
        return suggestion;
    },
});
