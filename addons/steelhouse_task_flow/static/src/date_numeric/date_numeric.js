import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { formatDate, formatDateTime } from "@web/views/fields/formatters";

// Odoo 19 shows dates "the human way" (current year without the year, month by name). For Georgian
// the browser has no short month names, so it showed "M11 20". Always use the language's date format
// instead (ka_GE: 20.11.2026) - on forms (date fields) and in lists / other views (formatters).
patch(DateTimeField.prototype, {
    getFormattedValue(valueIndex) {
        return super.getFormattedValue(valueIndex, true);
    },
});

const numericDate = (value, options = {}) => formatDate(value, { ...options, numeric: true });
numericDate.extractOptions = formatDate.extractOptions;
const numericDateTime = (value, options = {}) => formatDateTime(value, { ...options, numeric: true });
numericDateTime.extractOptions = formatDateTime.extractOptions;

registry
    .category("formatters")
    .add("date", numericDate, { force: true })
    .add("datetime", numericDateTime, { force: true });
