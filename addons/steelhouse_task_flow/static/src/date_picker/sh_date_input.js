import { Component } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";

const { DateTime } = luxon;

// A date box for our own widgets: opens Odoo's calendar instead of the browser's own one
// (<input type="date">). The value goes in and out as "YYYY-MM-DD" ("" = empty).
export class ShDateInput extends Component {
    static template = "steelhouse_task_flow.ShDateInput";
    static components = { DateTimeInput };
    static props = {
        value: { optional: true },
        onChange: Function,
        class: { type: String, optional: true },
        placeholder: { type: String, optional: true },
    };

    get date() {
        const date = this.props.value ? DateTime.fromISO(this.props.value) : false;
        return date && date.isValid ? date : false;
    }

    get cssClass() {
        return `o_sh_date_input ${this.props.class || ""}`;
    }

    onApply(value) {
        const iso = value && value.isValid ? value.toISODate() : "";
        if (iso !== (this.props.value || "")) {
            this.props.onChange(iso);
        }
    }
}
