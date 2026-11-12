import { patch } from "@web/core/utils/patch";
import { WarningDialog } from "@web/core/errors/error_dialogs";

// The "deputy is on leave" message (hr.leave.delegation._sh_absence_message):
// „<name>“ ამ დღეებში თვითონ არის შვებულებაში: <type>, <dates> (<status>). <hint>
const DEPUTY_ABSENT = /^„(.+?)“ ამ დღეებში თვითონ არის შვებულებაში: (.+), (\d{2}\.\d{2}\.\d{4}(?: – \d{2}\.\d{2}\.\d{4})?) \((.+?)\)\. ([\s\S]+)$/;
const STATUS_CLASS = {
    "დამტკიცებული": "o_sh_dep_status_ok",
    "დასამტკიცებელი": "o_sh_dep_status_wait",
    "მეორე დამტკიცება": "o_sh_dep_status_wait",
};

// Show that message as a card (same text, nicer look); every other warning stays as it is.
patch(WarningDialog.prototype, {
    setup() {
        super.setup(...arguments);
        const match = typeof this.message === "string" && this.message.trim().match(DEPUTY_ABSENT);
        if (match) {
            const [, name, type, dates, status, hint] = match;
            this.shDeputy = {
                name,
                initial: name.trim().charAt(0),
                type,
                dates,
                status,
                statusClass: STATUS_CLASS[status] || "o_sh_dep_status_wait",
                hint: hint.trim(),
            };
            this.title = "შემცვლელი შვებულებაშია";
        }
    },
});
