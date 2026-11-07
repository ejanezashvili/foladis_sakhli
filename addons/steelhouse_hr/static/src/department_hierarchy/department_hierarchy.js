import { Component, onWillStart, useEffect, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { HierarchyCard } from "@web_hierarchy/hierarchy_card";
import { HierarchyRenderer } from "@web_hierarchy/hierarchy_renderer";
import { hierarchyView } from "@web_hierarchy/hierarchy_view";

/**
 * Department card whose open/close button also works for departments that only
 * have positions (no sub-departments).
 */
export class DepartmentCard extends HierarchyCard {
    static template = "steelhouse_hr.DepartmentCard";
    static props = {
        ...HierarchyCard.props,
        isOpen: Boolean,
        canOpen: Boolean,
        count: Number,
        onToggle: Function,
    };
}

/**
 * One department card. When opened, its positions (with the people holding them)
 * and its sub-departments are shown in a frame right under the row that contains
 * the card. The template has two roots (card + panel) so both sit in the parent grid.
 */
export class DepartmentTreeNode extends Component {
    static template = "steelhouse_hr.DepartmentTreeNode";
    static components = { DepartmentCard };
    static props = {
        node: Object,
        openRecord: Function,
        archInfo: Object,
        shared: Object,
        isRoot: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.shared = useState(this.props.shared);
        this.cardRef = useRef("card");
        this.panelRef = useRef("panel");
        useEffect(() => this.placeArrow());
        useExternalListener(window, "resize", () => this.placeArrow());
    }

    get positions() {
        return this.props.isRoot ? [] : this.shared.positions[this.props.node.resId] || [];
    }

    get isOpen() {
        return this.props.node.nodes.length > 0 || !!this.shared.open[this.props.node.id];
    }

    get canOpen() {
        const node = this.props.node;
        return node.nodes.length > 0 || node.canShowChildNodes || this.positions.length > 0;
    }

    get count() {
        return this.props.node.childResIds.length + this.positions.length;
    }

    async toggle() {
        const node = this.props.node;
        const open = this.shared.open;
        if (this.isOpen) {
            delete open[node.id];
            if (node.nodes.length) {
                node.collapseChildNodes();
            }
            return;
        }
        // one open card per level, like the standard view
        for (const sibling of node.parentNode?.nodes || []) {
            if (sibling !== node) {
                delete open[sibling.id];
                if (sibling.nodes.length) {
                    sibling.collapseChildNodes();
                }
            }
        }
        open[node.id] = true;
        if (node.canShowChildNodes) {
            await node.showChildNodes();
        }
    }

    async openEmployee(employeeId) {
        const action = await this.orm.call("hr.employee", "get_formview_action", [[employeeId]]);
        this.action.doAction(action);
    }

    // Center the frame under the opened card (kept inside the page width)
    // and point its arrow at the card.
    placeArrow() {
        const card = this.cardRef.el;
        const panel = this.panelRef.el;
        if (!card || !panel || this.props.isRoot) {
            return;
        }
        const frame = panel.querySelector(":scope > .o_sh_tree_frame");
        const COL = 250, GAP = 12, PAD = 14;
        const items = this.props.node.nodes.length + this.positions.length;
        // nested frames may be wider than the frame they sit in (it grows), up to the page width
        const tree = panel.closest(".o_sh_dept_tree");
        const avail = (tree ? tree.clientWidth - 40 : panel.clientWidth) - 2 * PAD - 4;
        const cols = Math.max(1, Math.min(items, Math.floor((avail + GAP) / (COL + GAP))));
        frame.style.setProperty("--sh-cols", cols);
        const width = cols * COL + (cols - 1) * GAP + 2 * PAD + 4;
        const c = card.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        const center = c.left + c.width / 2 - p.left;
        const left = Math.max(0, Math.min(center - width / 2, Math.max(panel.clientWidth, width) - width));
        frame.style.marginLeft = `${left}px`;
        frame.style.setProperty("--sh-arrow-left", `${center - left}px`);
    }
}
DepartmentTreeNode.components.DepartmentTreeNode = DepartmentTreeNode;

export class DepartmentHierarchyRenderer extends HierarchyRenderer {
    static template = "steelhouse_hr.DepartmentHierarchyRenderer";
    static components = { ...HierarchyRenderer.components, DepartmentTreeNode };

    setup() {
        super.setup();
        this.shared = useState({ positions: {}, open: {} });
        const orm = useService("orm");
        onWillStart(async () => {
            this.shared.positions = await orm.call("hr.department", "sh_positions_data", []);
        });
    }

    // Drag & drop of the default view works on rows; this layout has no rows.
    get canDragAndDropRecord() {
        return false;
    }
}

export const departmentHierarchyView = {
    ...hierarchyView,
    Renderer: DepartmentHierarchyRenderer,
};

registry.category("views").add("steelhouse_department_hierarchy", departmentHierarchyView);
