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
        const sep = (localization.decimalPoint || ".").replace(/[.*+?^${}()|[\]\]/g, "\$&");
        return value
            .replace(new RegExp(`(${sep}\d*?[1-9])0+$`), "$1")
            .replace(new RegExp(`${sep}0+$`), "");
    }
}

registry
    .category("fields")
    .add("float_without_trailing_zeros", { ...floatField, component: ShFloatWithoutTrailingZeros }, { force: true });
