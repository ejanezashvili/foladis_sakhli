import { Message } from "@mail/core/common/message";
import { messageActionsRegistry, registerMessageAction } from "@mail/core/common/message_actions";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { toRaw } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

// Desktop: more buttons visible on a message (Odoo shows 3, the rest goes to "...").
patch(Message.prototype, {
    get quickActionCount() {
        const count = super.quickActionCount;
        return count === 4 ? 6 : count;
    },
});

// "Reply" right after "mark as read" (Odoo puts it last in the Inbox).
const reply = messageActionsRegistry.get("reply-to");
messageActionsRegistry.add("reply-to", { ...reply, sequence: ({ message }) => (message.isSelfAuthored ? 55 : 45) }, { force: true });

// Inbox: mark as done the activities that this notification is about (assigned to me on that record).
registerMessageAction("sh-activity-done", {
    condition: ({ message, store, thread }) =>
        thread?.eq(store.inbox) && message.model && message.res_id && message.model !== "discuss.channel",
    icon: "fa fa-check-square-o",
    name: "შესრულებულად მონიშვნა",
    sequence: 41,
    async onSelected({ message: msg, owner }) {
        const message = toRaw(msg);
        const { orm, dialog, notification } = owner.env.services;
        const acts = await orm.call("mail.activity", "sh_my_open_activities", [message.model, message.res_id]);
        if (!acts.length) {
            notification.add("ამ ჩანაწერზე თქვენთვის ღია აქტივობა აღარ არის.", { type: "info" });
            return;
        }
        const list = acts.map((a) => `• ${a.name}${a.note ? " — " + a.note : ""} (ვადა: ${a.deadline})`).join("\n");
        dialog.add(ConfirmationDialog, {
            title: "შესრულებულად მონიშვნა",
            body: `მოინიშნოს შესრულებულად?\n\n${list}`,
            confirmLabel: "შესრულდა",
            cancelLabel: "გაუქმება",
            confirm: async () => {
                await orm.call("mail.activity", "action_feedback", [acts.map((a) => a.id)]);
                message.setDone();
                notification.add("შესრულებულად მოინიშნა.", { type: "success" });
            },
            cancel: () => {},
        });
    },
});
