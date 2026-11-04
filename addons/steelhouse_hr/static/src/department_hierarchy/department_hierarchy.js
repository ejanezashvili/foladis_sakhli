import { Component, useEffect, useExternalListener, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { HierarchyCard } from "@web_hierarchy/hierarchy_card";
import { HierarchyRenderer } from "@web_hierarchy/hierarchy_renderer";
import { hierarchyView } from "@web_hierarchy/hierarchy_view";

/**
 * One department card. When opened, its sub-departments are shown in a panel
 * right under the row that contains the card (the card itself stays in place).
 * The template has two roots (card + panel) so both sit in the parent grid.
 */
export class DepartmentTreeNode extends Component {
    static template = "steelhouse_hr.DepartmentTreeNode";
    static components = { HierarchyCard };
    static props = {
        node: Object,
        openRecord: Function,
        archInfo: Object,
        isRoot: { type: Boolean, optional: true },
    };

    setup() {
        this.cardRef = useRef("card");
        this.panelRef = useRef("panel");
        useEffect(() => this.placeArrow());
        useExternalListener(window, "resize", () => this.placeArrow());
    }

    // Center the sub-departments frame under the opened card (kept inside the page width)
    // and point its arrow at the card.
    placeArrow() {
        const card = this.cardRef.el;
        const panel = this.panelRef.el;
        if (!card || !panel || this.props.isRoot) {
            return;
        }
        const frame = panel.querySelector(":scope > .o_sh_tree_frame");
        const COL = 250, GAP = 12, PAD = 14;
        const avail = panel.clientWidth - 2 * PAD - 4;
        const cols = Math.max(1, Math.min(this.props.node.nodes.length, Math.floor((avail + GAP) / (COL + GAP))));
        frame.style.setProperty("--sh-cols", cols);
        const width = cols * COL + (cols - 1) * GAP + 2 * PAD + 4;
        const c = card.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        const center = c.left + c.width / 2 - p.left;
        const left = Math.max(0, Math.min(center - width / 2, panel.clientWidth - width));
        frame.style.marginLeft = `${left}px`;
        frame.style.setProperty("--sh-arrow-left", `${center - left}px`);
    }
}
DepartmentTreeNode.components.DepartmentTreeNode = DepartmentTreeNode;

export class DepartmentHierarchyRenderer extends HierarchyRenderer {
    static template = "steelhouse_hr.DepartmentHierarchyRenderer";
    static components = { ...HierarchyRenderer.components, DepartmentTreeNode };

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
