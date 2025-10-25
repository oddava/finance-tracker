from aiogram.utils.i18n import gettext as _


# ------------- Broadcast -------------- #
def get_broadcast_sent_text(status) -> str:
    return _(
        "✅ Successfully sent broadcast message to <b>{user_count}</b> users. \n\nFailed: {failed_count}\nBlocked: {blocked_count}").format(
        user_count=status["total"], failed_count=status["failed"], blocked_count=status["blocked"])


def get_confirm_broadcast_text(total_users: int, text: str) -> str:
    return _(f"📢 <b>Confirm Broadcast</b>\n\n"
             "<b>Recipients:</b> {total_users:,} users\n\n"
             "<b>Message:</b>\n{text}\n\n"
             f"Send this message to all users?").format(total_users=total_users, text=text)


def get_broadcast_message() -> str:
    return _("📢 <b>Broadcast Message</b>\n\n"
             "To send a broadcast message to all users:\n\n"
             "Use command: <code>/broadcast your message here</code>\n\n"
             "⚠️ <b>Warning:</b> This will send the message to ALL users!")
