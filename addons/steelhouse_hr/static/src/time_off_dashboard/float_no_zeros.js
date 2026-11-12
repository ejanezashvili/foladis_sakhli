import { registry } from "@web/core/registry";
import { localization } from "@web/core/l10n/localization";
import { floatField, FloatField } from "@web/views/fields/float/float_field";

/**
 * Odoo's "float_without_trailing_zeros" (accrual plan levels: "2", not "2,00000") only strips
 * zeros after a "." - with the Georgian "," it showed "2,00000". Same widget, any decimal sign.
 */
class ShFloatWithoutTrailingZeros extends FloatField {
    get formattedValue() {
        const value = super.formattedValue;
        if (typeof value !== "string") {
            return value;
        }
        const sep = localization.decimalPoint || ".";
        let result = value;
        const at = result.lastIndexOf(sep);
        if (at !== -1 && /^\d+$/.test(result.slice(at + sep.length))) {
            // drop zeros at the end of the decimals, then the sign itself if nothing is left
            result = result.replace(/0+$/, "");
            if (result.endsWith(sep)) {
                result = result.slice(0, -sep.length);
            }
        }
        return result;
    }
}

registry
    .category("fields")
    .add("float_without_trailing_zeros", { ...floatField, component: ShFloatWithoutTrailingZeros }, { force: true });
