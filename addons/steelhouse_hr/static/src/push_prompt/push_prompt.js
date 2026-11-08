import { MessagingMenu } from "@mail/core/public_web/messaging_menu";
import { patch } from "@web/core/utils/patch";
import "@mail/core/web/messaging_menu_patch";

// Browser push notifications need HTTPS. While the site runs on plain HTTP the
// "Turn on notifications" prompt can never succeed and keeps a "1" on the chat icon,
// so it is hidden until HTTPS is set up (then Odoo's standard prompt comes back).
patch(MessagingMenu.prototype, {
    get shouldAskPushPermission() {
        return window.isSecureContext && super.shouldAskPushPermission;
    },
});
