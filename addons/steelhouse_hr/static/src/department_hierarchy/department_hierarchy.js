import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { HierarchyCard } from "@web_hierarchy/hierarchy_card";
import { HierarchyRenderer } from "@web_hierarchy/hierarchy_renderer";
import { hierarchyView } from "@web_hierarchy/hierarchy_view";

/**
 * One department card with its sub-departments shown right under it.
 */
export class DepartmentTreeNode extends Component {
    static template = "steelhouse_hr.DepartmentTreeNode";
    static components = { HierarchyCard };
    static props = {
        node: Object,
        openRecord: Function,
        archInfo: Object,
    };
}
DepartmentTreeNode.components.DepartmentTreeNode = DepartmentTreeNode;

/**
 * Department hierarchy: children open directly under the card
 * (Odoo's default opens them in a new row at the bottom).
 */
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
