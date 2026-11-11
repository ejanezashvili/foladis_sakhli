import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Search box with avatars, like Odoo's many2one user field
export class ShUserPicker extends Component {
    static template = "steelhouse_task_flow.ShUserPicker";
    static props = { users: Array, value: { optional: true }, onChange: Function };

    setup() {
        this.state = useState({ open: false, term: "", all: false });
    }
    get current() {
        return this.props.users.find((u) => u.id === this.props.value);
    }
    get matches() {
        const term = this.state.term.trim().toLowerCase();
        const list = term ? this.props.users.filter((u) => u.name.toLowerCase().includes(term)) : this.props.users;
        return this.state.all ? list : list.slice(0, 8);
    }
    get hasMore() {
        const term = this.state.term.trim().toLowerCase();
        const n = term ? this.props.users.filter((u) => u.name.toLowerCase().includes(term)).length : this.props.users.length;
        return !this.state.all && n > 8;
    }
    avatar(id) {
        return `/web/image/res.users/${id}/avatar_128`;
    }
    onFocus(ev) {
        this.state.open = true;
        this.state.all = false;
        this.state.term = "";
        ev.target.select();
    }
    onInput(ev) {
        this.state.term = ev.target.value;
        this.state.open = true;
    }
    onBlur(ev) {
        this.state.open = false;
        ev.target.value = this.current ? this.current.name : "";
    }
    pick(user) {
        this.state.open = false;
        this.props.onChange(user ? user.id : false);
    }
}

// "ქვედავალებები" tab: sub-tasks grouped by work stages (sections), like a checklist.
export class TaskSteps extends Component {
    static template = "steelhouse_task_flow.TaskSteps";
    static props = { ...standardFieldProps };
    static components = { ShUserPicker };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ sections: [], users: [], folded: {}, loaded: false });
        onWillStart(() => this.load());
    }

    get taskId() {
        return this.props.record.resId;
    }

    async call(method, args = []) {
        try {
            return await this.orm.call("project.task", method, [[this.taskId], ...args]);
        } catch (e) {
            await this.load();
            throw e;
        }
    }

    async load() {
        if (!this.taskId) {
            this.state.loaded = true;
            return;
        }
        const data = await this.orm.call("project.task", "sh_steps_data", [[this.taskId]]);
        this.state.sections = data.sections;
        this.state.users = data.users;
        this.state.loaded = true;
    }

    get showDone() {
        // "დაასრულა" column appears only once a stage has all its sub-tasks done
        return this.state.sections.some((s) => s.items.length && this.doneCount(s) === s.items.length);
    }
    doneCount(section) {
        return section.items.filter((i) => i.done).length;
    }
    percent(section) {
        return section.items.length ? Math.round((100 * this.doneCount(section)) / section.items.length) : 0;
    }
    sectionState(section) {
        const done = this.doneCount(section);
        if (section.items.length && done === section.items.length) {
            return "done";
        }
        return done ? "current" : "todo";
    }
    toggleFold(section) {
        this.state.folded[section.id] = !this.state.folded[section.id];
    }

    async addSection() {
        await this.call("sh_steps_add_section");
        await this.load();
    }
    async renameSection(section, ev) {
        const name = ev.target.value;
        if (name === section.name) {
            return;
        }
        await this.call("sh_steps_rename_section", [section.id, name]);
        section.name = name;
    }
    async writeSection(section, vals) {
        await this.call("sh_steps_write_section", [section.id, vals]);
        await this.load();
    }
    onSectionUser(section, userId) {
        this.writeSection(section, { user_id: userId || false });
    }
    onSectionDeadline(section, ev) {
        this.writeSection(section, { deadline: ev.target.value || false });
    }
    deleteSection(section) {
        this.dialog.add(ConfirmationDialog, {
            title: "დარწმუნებული ხარ?",
            body: `ეტაპი „${section.name || "უსახელო"}“ წაიშლება.`,
            confirmLabel: "კი, წაიშალოს",
            cancelLabel: "არა",
            confirm: async () => {
                await this.call("sh_steps_delete_section", [section.id]);
                await this.load();
            },
            cancel: () => {},
        });
    }

    async addItem(section) {
        await this.call("sh_steps_add_item", [section.id || false]);
        this.state.folded[section.id] = false;
        await this.load();
    }
    async writeItem(item, vals) {
        await this.call("sh_steps_write_item", [item.id, vals]);
        await this.load();
    }
    onName(item, ev) {
        if (ev.target.value !== item.name) {
            this.writeItem(item, { name: ev.target.value });
        }
    }
    onUser(item, userId) {
        this.writeItem(item, { user_id: userId || false });
    }
    onDeadline(item, ev) {
        this.writeItem(item, { deadline: ev.target.value || false });
    }
    toggle(item) {
        const done = !item.done;
        this.dialog.add(ConfirmationDialog, {
            title: "დარწმუნებული ხარ?",
            body: done
                ? `ქვედავალება „${item.name}“ მოინიშნება როგორც შესრულებული.`
                : `ქვედავალება „${item.name}“ დაბრუნდება შეუსრულებელში.`,
            confirmLabel: done ? "კი, შესრულდა" : "კი, დაბრუნდეს",
            cancelLabel: "არა",
            confirm: async () => {
                await this.call("sh_steps_toggle", [item.id, done]);
                await this.load();
                await this.props.record.load();
            },
            cancel: () => {},
        });
    }
    deleteItem(item) {
        this.dialog.add(ConfirmationDialog, {
            title: "დარწმუნებული ხარ?",
            body: `ქვედავალება „${item.name}“ წაიშლება.`,
            confirmLabel: "კი, წაიშალოს",
            cancelLabel: "არა",
            confirm: async () => {
                await this.call("sh_steps_delete_item", [item.id]);
                await this.load();
            },
            cancel: () => {},
        });
    }
}

registry.category("fields").add("sh_task_steps", {
    component: TaskSteps,
    supportedTypes: ["char"],
});
