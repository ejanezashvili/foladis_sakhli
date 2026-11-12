import { registry } from "@web/core/registry";
import { localization } from "@web/core/l10n/localization";
import { formatFloat } from "@web/views/fields/formatters";
import { floatField, FloatField } from "@web/views/fields/float/float_field";

/**
 * Day counts without useless zeros: "24", "0", "1,5" - not "24,0" / "2,00000".
 * Odoo's own "float_without_trailing_zeros" only strips zeros after a "." (the Georgian
 * decimal sign is ","), so the widget is registered again, plus a formatter of the same
 * name for list totals.
 */
export function shStripZeros(value) {
    if (typeof value !== "string") {
        return value;
    }
    const sep = localization.decimalPoint || ".";
    const at = value.lastIndexOf(sep);
    if (at === -1 || !/^\d+$/.test(value.slice(at + sep.length))) {
        return value;
    }
    let result = value.replace(/0+$/, "");
    if (result.endsWith(sep)) {
        result = result.slice(0, -sep.length);
    }
    return result;
}

class ShFloatWithoutTrailingZeros extends FloatField {
    get formattedValue() {
        return shStripZeros(super.formattedValue);
    }
}

registry
    .category("fields")
    .add("float_without_trailing_zeros", { ...floatField, component: ShFloatWithoutTrailingZeros }, { force: true });

// list totals of such columns
registry
    .category("formatters")
    .add("float_without_trailing_zeros", (value, options) => shStripZeros(formatFloat(value, options)), { force: true });
