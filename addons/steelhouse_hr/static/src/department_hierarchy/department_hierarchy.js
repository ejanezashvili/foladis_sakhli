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
    };

    setup() {
        this.cardRef = useRef("card");
        this.panelRef = useRef("panel");
        useEffect(() => this.placeArrow());
        useExternalListener(window, "resize", () => this.placeArrow());
    }

    // Point the panel's arrow at the opened card.
    placeArrow() {
        const card = this.cardRef.el;
        const panel = this.panelRef.el;
        if (!card || !panel) {
            return;
        }
        const c = card.getBoundingClientRect();
        const p = panel.getBoundingClientRect();
        panel.style.setProperty("--sh-arrow-left", `${c.left + c.width / 2 - p.left}px`);
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
