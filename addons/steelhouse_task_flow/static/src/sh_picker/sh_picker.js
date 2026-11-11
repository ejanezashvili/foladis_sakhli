import { patch } from "@web/core/utils/patch";
import { Domain } from "@web/core/domain";
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

// "პროექტები" (all tasks) page, action context key `sh_picker`:
// the "Group By" column of the search menu shows only employee / department / customer.
// Clicking one opens a dialog (with search) to pick specific records; the pick becomes a filter.
const PICKERS = [
    {
        key: "employee",
        label: "თანამშრომელი",
        resModel: "res.users",
        dialogDomain: [["share", "=", false]],
        domain: (ids) => [["user_ids", "in", ids]],
    },
    {
        key: "department",
        label: "დეპარტამენტი",
        resModel: "hr.department",
        dialogDomain: [],
        domain: (ids) => [["sh_department_id", "child_of", ids]],
    },
    {
        key: "customer",
        label: "კლიენტი",
        resModel: "res.partner",
        dialogDomain: ["&", ["employee_ids", "=", false], "|", ["user_ids", "=", false], ["user_ids.share", "=", true]],
        domain: (ids) => [["partner_id", "in", ids]],
    },
];

patch(SearchBarMenu.prototype, {
    get shPicker() {
        return Boolean(this.env.searchModel.globalContext?.sh_picker);
    },
    get shPickers() {
        return PICKERS;
    },
    onShPick(picker) {
        this.env.services.dialog.add(SelectCreateDialog, {
            resModel: picker.resModel,
            domain: picker.dialogDomain,
            title: picker.label,
            multiSelect: true,
            noCreate: true,
            context: { active_test: true },
            onSelected: async (ids) => {
                if (!ids.length) {
                    return;
                }
                const records = await this.env.services.orm.read(picker.resModel, ids, ["display_name"]);
                this.env.searchModel.createNewFilters([
                    {
                        description: `${picker.label}: ${records.map((r) => r.display_name).join(" ან ")}`,
                        domain: new Domain(picker.domain(ids)).toString(),
                    },
                ]);
            },
        });
    },
});
