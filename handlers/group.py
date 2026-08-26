import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ChatType

from utils.auth import is_allowed_or_owner
from utils.helpers import (
    is_topic_capture_active,
    set_topic_capture_mode,
    load_config,
    save_config,
    redeem_session,
    get_pending_session,
)
from models.config_model import BotConfig
from keyboards.main_menu import destination_confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


_NOT_STARTED_VISIBLE = (
    "⚠️ Destination setup has not been started.\n\n"
    "Open the bot's private chat → Set Destination and choose the appropriate "
    "Normal / Visible Setup.\n"
    "Then return here and send /setdestination."
)

_NOT_STARTED_ANON = (
    "⚠️ Destination setup has not been started.\n\n"
    "Open the bot's private chat → Set Destination and choose Anonymous Admin Setup.\n"
    "Then return here and send the generated setup command."
)

_TOKEN_INVALID = (
    "⚠️ This setup command is invalid or has expired.\n"
    "Generate a new one from Set Destination in the bot's private chat."
)


def _resolve_destination(message: Message) -> tuple[int, str, int | None, str]:
    """
    Detect destination type/thread from the current message's chat, without
    saving anything. Returns (chat_id, chat_title, thread_id, destination_type).
    destination_type: "normal_group" | "forum_topic" | "forum_general"
    """
    chat_id = message.chat.id
    chat_title = message.chat.title or str(chat_id)
    is_forum = getattr(message.chat, "is_forum", False)

    if not is_forum:
        return chat_id, chat_title, None, "normal_group"

    thread_id = message.message_thread_id
    # Minimal, targeted debug log to verify General-topic payload shape on a
    # real client before this condition is trusted long-term. Intentionally
    # narrow — only fires for forum chats, not broad request logging.
    logger.info(
        "[dest-detect] forum chat_id=%s is_forum=%s message_thread_id=%s is_topic_message=%s",
        chat_id, is_forum, thread_id, getattr(message, "is_topic_message", None),
    )
    if not thread_id:
        return chat_id, chat_title, None, "forum_general"
    return chat_id, chat_title, thread_id, "forum_topic"


@router.message(Command("setdestination"))
async def cmd_setdestination(message: Message, bot: Bot) -> None:
    """
    Handles /setdestination sent inside a forum topic, General topic, or
    normal group. Two independent paths:

    - Visible sender: unchanged existing behavior — requires the
      Normal/Visible Setup capture flag armed via private chat, keyed on the
      sender's real user_id. No token involved, session collection is never
      queried on this path.
    - Anonymous admin sender (sender_chat == this chat): the real user_id is
      not available from Telegram, so a setup token generated in private
      chat is required. Redeeming it is atomic and does NOT save the
      destination immediately — it lands in "pending" state and a
      confirmation prompt is sent to the token owner's private chat only.
    """
    if not await is_allowed_or_owner(message):
        return

    chat_type = message.chat.type
    if chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await message.reply(
            "⚠️ This command must be sent inside a group or supergroup, not in private chat."
        )
        return

    is_anonymous = message.sender_chat is not None and message.sender_chat.id == message.chat.id

    # Parse optional token argument, e.g. "/setdestination H7K9P2MX"
    parts = (message.text or "").split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else None

    if not is_anonymous:
        # ── Visible sender: existing user_id-based workflow, unchanged ──
        user_id = message.from_user.id

        if token:
            # Visible users never need a token — reject politely without
            # touching the sessions collection at all.
            await message.reply(
                "ℹ️ You're using Normal / Visible Setup.\n"
                "Please send /setdestination without a code."
            )
            return

        if not await is_topic_capture_active(user_id):
            await message.reply(_NOT_STARTED_VISIBLE)
            return

        chat_id, chat_title, thread_id, dest_type = _resolve_destination(message)

        cfg = await load_config(user_id)
        cfg.user_id = user_id
        cfg.destination_chat_id = chat_id
        cfg.destination_title = chat_title
        cfg.destination_type = dest_type
        cfg.destination_thread_id = thread_id
        await save_config(cfg)

        await set_topic_capture_mode(user_id, False)
        await message.reply(_success_text(dest_type, chat_title, chat_id, thread_id), parse_mode="HTML")
        logger.info(
            "[user=%s] Destination set via visible setup: type=%s chat_id=%s thread_id=%s",
            user_id, dest_type, chat_id, thread_id,
        )
        return

    # ── Anonymous admin sender: token-bridge workflow ──
    if not token:
        await message.reply(_NOT_STARTED_ANON)
        return

    chat_id, chat_title, thread_id, dest_type = _resolve_destination(message)
    session_mode = "topic" if dest_type in ("forum_topic", "forum_general") else "normal_group"

    session = await redeem_session(
        token=token,
        mode=session_mode,
        resolved_chat_id=chat_id,
        resolved_title=chat_title,
        resolved_thread_id=thread_id,
        resolved_type=dest_type,
    )
    if session is None:
        # Covers: unknown token, expired, already used, and mode mismatch —
        # deliberately one generic message for all of these so a wrong
        # guess can't be used to probe which condition failed.
        await message.reply(_TOKEN_INVALID)
        return

    # Do NOT save yet — confirmation goes to the token owner's private chat only.
    try:
        if dest_type == "forum_general":
            detail = "📌 Topic: General\n"
        elif dest_type == "forum_topic":
            detail = f"📌 Thread ID: <code>{thread_id}</code>\n"
        else:
            detail = ""
        await bot.send_message(
            chat_id=session.user_id,
            text=(
                "🔗 <b>Destination detected</b>\n\n"
                f"🏷 Group: <b>{chat_title}</b>\n"
                f"{detail}\n"
                "Is this your destination?"
            ),
            reply_markup=destination_confirm_keyboard(token),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Could not deliver destination confirmation to user %s: %s", session.user_id, e)
        await message.reply(
            "⚠️ Couldn't reach your private chat to confirm this destination. "
            "Please open the bot's private chat first, then try the setup command again."
        )
        return

    # Neutral acknowledgement in the group — no destination/identity details exposed here.
    await message.reply("✅ Setup command received. Please confirm in the bot's private chat.")
    logger.info(
        "[token=%s] Anonymous destination redeemed, pending confirmation: chat_id=%s thread_id=%s type=%s",
        token, chat_id, thread_id, dest_type,
    )


def _success_text(dest_type: str, chat_title: str, chat_id: int, thread_id: int | None) -> str:
    if dest_type == "forum_general":
        return (
            "✅ <b>Destination General topic saved!</b>\n\n"
            f"🏷 Group: <b>{chat_title}</b>\n"
            f"🆔 Group ID: <code>{chat_id}</code>\n"
            "📌 Topic: General\n\n"
            "You can now use Range Forward in the bot's private chat."
        )
    if dest_type == "forum_topic":
        return (
            "✅ <b>Destination topic saved!</b>\n\n"
            f"🏷 Group: <b>{chat_title}</b>\n"
            f"🆔 Group ID: <code>{chat_id}</code>\n"
            f"📌 Thread ID: <code>{thread_id}</code>\n\n"
            "You can now use Range Forward in the bot's private chat."
        )
    return (
        "✅ <b>Destination group saved!</b>\n\n"
        f"🏷 Group: <b>{chat_title}</b>\n"
        f"🆔 Group ID: <code>{chat_id}</code>\n\n"
        "You can now use Range Forward in the bot's private chat."
    )
