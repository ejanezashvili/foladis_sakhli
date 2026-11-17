import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { registry } from "@web/core/registry";
import { ControlPanel } from "@web/search/control_panel/control_panel";

// Task pages: a green "Excel ▾" button right of the search bar with the two items of the ⚙ menu
// ("ჩანაწერების იმპორტი", "ყველას ექსპორტი") - the very same items, just at hand.
const KEYS = ["import-menu", "export-all-menu"];

export class ShExcelMenu extends Component {
    static template = "steelhouse_task_flow.ShExcelMenu";
    static components = { Dropdown };
    static props = {};

    setup() {
        this.items = [];
        onWillStart(() => this.loadItems());
        onWillUpdateProps(() => this.loadItems());
    }

    async loadItems() {
        const cog = registry.category("cogMenu");
        const items = [];
        for (const key of KEYS) {
            if (!cog.contains(key)) {
                continue;
            }
            const item = cog.get(key);
            const shown = "isDisplayed" in item ? await item.isDisplayed(this.env) : true;
            if (shown) {
                items.push({ key, Component: item.Component });
            }
        }
        this.items = items;
    }
}

ControlPanel.components = { ...ControlPanel.components, ShExcelMenu };
