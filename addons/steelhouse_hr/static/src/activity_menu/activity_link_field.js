import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";

/**
 * "Linked to" of an activity, e.g. "Paid Time Off-ის მინიჭება: 24.00 დღე — ანა ხაბულიანი",
 * shown in parts: title (muted), amount (green pill), person (bold). Same text, look only;
 * names in another shape are shown as they are.
 */
export class ActivityLinkField extends CharField {
    static template = "steelhouse_hr.ActivityLinkField";

    get shParts() {
        const text = this.props.record.data[this.props.name] || "";
        const match = text.match(/^(.+?): (.+?) — (.+)$/);
        return match ? { title: match[1], amount: match[2], person: match[3] } : null;
    }
}

const charField = registry.category("fields").get("char");
registry.category("fields").add("sh_activity_link", { ...charField, component: ActivityLinkField });
