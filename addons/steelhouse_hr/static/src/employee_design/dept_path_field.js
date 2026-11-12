import { registry } from "@web/core/registry";
import { Many2OneField } from "@web/views/fields/many2one/many2one_field";

/**
 * Department shown as its path ("Company > Unit > Sub-unit") with chips.
 * Only the look changes: when the field is edited, the standard many2one is used.
 */
export class DeptPathField extends Many2OneField {
    static template = "steelhouse_hr.DeptPathField";

    get shPath() {
        const value = this.props.record.data[this.props.name];
        const name = value && (value.display_name ?? value[1]);
        return name ? name.split(" / ") : [];
    }
}

const many2one = registry.category("fields").get("many2one");
registry.category("fields").add("sh_dept_path", { ...many2one, component: DeptPathField });
