import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

// Task boards: each column keeps its own colour wherever it is moved. The colour follows the stage
// name (same colours as the status pills); other columns ("დღეს", "ეს კვირა"...) get a stable colour
// computed from their name. Only a data attribute is set - the look is in task_card.scss.
const KIND_BY_NAME = {
    "ახალი": "new",
    "მიღებული": "accepted",
    "მიმდინარე": "in_progress",
    "შეჩერებული": "on_hold",
    "შემოწმებაზე": "review",
    "დაბრუნებული": "returned",
    "დასრულებული": "done",
    "გაუქმებული": "cancelled",
};

function stageKey(title) {
    if (KIND_BY_NAME[title]) {
        return KIND_BY_NAME[title];
    }
    let h = 0;
    for (const ch of title) {
        h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    }
    return "c" + (h % 6);
}

patch(KanbanRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(() => {
            const root = this.rootRef && this.rootRef.el;
            if (!root || !root.classList.contains("o_kanban_project_tasks")) {
                return;
            }
            for (const group of root.querySelectorAll(".o_kanban_group")) {
                const title = (group.querySelector(".o_column_title")?.textContent || "").trim();
                if (title) {
                    group.dataset.shStage = stageKey(title);
                }
            }
        });
    },
});
