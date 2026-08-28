import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.types import Message

import secrets
import re

from database import col_config, col_state, col_settings, col_users, col_sessions
from models.config_model import BotConfig, ForwardingState, BotSettings, UserProfile, SetupSession
from config import config

logger = logging.getLogger(__name__)


# ─── Key helpers ──────────────────────────────────────────────────────────────
# Private bot used {"_id": "singleton"} for all collections.
# Multi-user bot keys every document by user_id instead.

def _user_key(user_id: int) -> dict:
    return {"_id": user_id}


# ─── BotConfig helpers ────────────────────────────────────────────────────────

async def load_config(user_id: int) -> BotConfig:
    doc = await col_config().find_one(_user_key(user_id))
    if doc is None:
        return BotConfig(user_id=user_id)
    return BotConfig.from_dict(doc)


async def save_config(cfg: BotConfig) -> None:
    await col_config().update_one(
        _user_key(cfg.user_id),
        {"$set": {**_user_key(cfg.user_id), **cfg.to_dict()}},
        upsert=True,
    )


# ─── ForwardingState helpers ──────────────────────────────────────────────────

async def load_state(user_id: int) -> ForwardingState:
    doc = await col_state().find_one(_user_key(user_id))
    if doc is None:
        return ForwardingState(user_id=user_id)
    return ForwardingState.from_dict(doc)


async def save_state(state: ForwardingState) -> None:
    await col_state().update_one(
        _user_key(state.user_id),
        {"$set": {**_user_key(state.user_id), **state.to_dict()}},
        upsert=True,
    )


async def checkpoint_message_id(user_id: int, message_id: int) -> None:
    """Update only last_processed_message_id for frequent checkpointing."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {"last_processed_message_id": message_id}},
        upsert=True,
    )


async def checkpoint_progress(
    user_id: int,
    message_id: int,
    failed_count: int,
    skipped_count: int,
) -> None:
    """
    Single-write checkpoint after each processed message.
    Persists last_processed_message_id together with failed/skipped counters
    so counters and checkpoint never drift apart across a crash.
    """
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {
            "last_processed_message_id": message_id,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        }},
        upsert=True,
    )


async def set_job_status(user_id: int, status: str) -> None:
    """Persist only the status field (idle/forwarding/recovering/cancelled/failed/completed)."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {"status": status}},
        upsert=True,
    )


async def save_progress_message_ref(user_id: int, chat_id: int, message_id: int) -> None:
    """Persist the single editable progress message's chat_id/message_id (Phase 3)."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {
            "progress_chat_id": chat_id,
            "progress_message_id": message_id,
        }},
        upsert=True,
    )


async def mark_pinned(user_id: int) -> None:
    """Persist pinned_done=True so a resumed job never pins a second message (Phase 2)."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {"pinned_done": True}},
        upsert=True,
    )


async def mark_completion_sent(user_id: int) -> None:
    """Persist completion_sent=True so 'That's it ♥️' is never sent twice (Phase 2)."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {"completion_sent": True}},
        upsert=True,
    )


async def set_job_started_at(user_id: int, started_at) -> None:
    """Persist job_started_at once, at fresh job creation (used for ETA math, Phase 3)."""
    await col_state().update_one(
        _user_key(user_id),
        {"$set": {"job_started_at": started_at}},
        upsert=True,
    )


async def is_stop_requested(user_id: int) -> bool:
    doc = await col_state().find_one(_user_key(user_id), {"stop_flag": 1})
    if doc is None:
        return False
    return doc.get("stop_flag", False)


# ─── BotSettings helpers ──────────────────────────────────────────────────────

async def load_settings(user_id: int) -> BotSettings:
    doc = await col_settings().find_one(_user_key(user_id))
    if doc is None:
        return BotSettings(user_id=user_id, delay_seconds=config.DEFAULT_DELAY_SECONDS)
    return BotSettings.from_dict(doc)


async def save_settings(settings: BotSettings) -> None:
    await col_settings().update_one(
        _user_key(settings.user_id),
        {"$set": {**_user_key(settings.user_id), **settings.to_dict()}},
        upsert=True,
    )


async def set_topic_capture_mode(user_id: int, enabled: bool) -> None:
    expiry = None
    if enabled:
        expiry = datetime.now(timezone.utc) + timedelta(seconds=config.TOPIC_CAPTURE_EXPIRY)
    await col_settings().update_one(
        _user_key(user_id),
        {"$set": {
            "topic_capture_mode": enabled,
            "topic_capture_expires": expiry,
        }},
        upsert=True,
    )


async def is_topic_capture_active(user_id: int) -> bool:
    doc = await col_settings().find_one(
        _user_key(user_id),
        {"topic_capture_mode": 1, "topic_capture_expires": 1}
    )
    if doc is None:
        return False
    if not doc.get("topic_capture_mode", False):
        return False
    expiry = doc.get("topic_capture_expires")
    if expiry is None:
        return False
    now = datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return now < expiry


# ─── UserProfile helpers (NEW) ────────────────────────────────────────────────

async def load_user(user_id: int) -> Optional[UserProfile]:
    """Load user profile. Returns None if user does not exist in DB."""
    doc = await col_users().find_one(_user_key(user_id))
    if doc is None:
        return None
    return UserProfile.from_dict(doc)


async def save_user(profile: UserProfile) -> None:
    await col_users().update_one(
        _user_key(profile.user_id),
        {"$set": {**_user_key(profile.user_id), **profile.to_dict()}},
        upsert=True,
    )


async def upsert_user_on_activity(message: Message) -> UserProfile:
    """
    Called whenever an allowed user runs a command.
    Creates profile on first interaction, updates last_seen and usage_count.
    Returns the current profile.
    """
    user = message.from_user
    user_id = user.id
    now = datetime.now(timezone.utc)

    existing = await load_user(user_id)
    if existing is None:
        # First time we see this user — create pending profile
        profile = UserProfile(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            status="pending",
            first_seen=now,
            last_seen=now,
            usage_count=1,
        )
    else:
        # Update existing profile
        profile = existing
        profile.username = user.username
        profile.first_name = user.first_name
        profile.last_seen = now
        profile.usage_count += 1

    await save_user(profile)
    return profile


async def set_user_status(user_id: int, status: str) -> bool:
    """
    Set user status to 'allowed', 'banned', or 'pending'.
    Returns True if user was found and updated, False if user not in DB.
    """
    result = await col_users().update_one(
        _user_key(user_id),
        {"$set": {"status": status}},
    )
    return result.matched_count > 0


async def get_all_users() -> list[UserProfile]:
    """Return all user profiles sorted by first_seen descending."""
    cursor = col_users().find({}).sort("first_seen", -1)
    docs = await cursor.to_list(length=200)
    return [UserProfile.from_dict(d) for d in docs]


async def get_users_by_status(status: str) -> list[UserProfile]:
    cursor = col_users().find({"status": status}).sort("first_seen", -1)
    docs = await cursor.to_list(length=200)
    return [UserProfile.from_dict(d) for d in docs]


async def count_users_by_status() -> dict:
    """Return counts for each status. Used in admin stats."""
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    cursor = col_users().aggregate(pipeline)
    results = await cursor.to_list(length=10)
    counts = {"allowed": 0, "banned": 0, "pending": 0}
    for r in results:
        counts[r["_id"]] = r["count"]
    return counts


# ─── Message ID extraction from forwarded messages ───────────────────────────
# Unchanged from private bot.

def extract_forwarded_message_id(message: Message) -> Optional[int]:
    """
    Extract the original message_id from a message forwarded from a channel.
    Handles both Bot API 7.0+ (forward_origin) and legacy (forward_from_message_id).
    """
    if message.forward_origin is not None:
        origin = message.forward_origin
        if hasattr(origin, "message_id") and origin.message_id:
            return origin.message_id
    if message.forward_from_message_id:
        return message.forward_from_message_id
    return None


def extract_forwarded_chat_id(message: Message) -> Optional[int]:
    if message.forward_origin is not None:
        origin = message.forward_origin
        if hasattr(origin, "chat") and origin.chat:
            return origin.chat.id
    if message.forward_from_chat:
        return message.forward_from_chat.id
    return None


def extract_forwarded_chat_title(message: Message) -> Optional[str]:
    if message.forward_origin is not None:
        origin = message.forward_origin
        if hasattr(origin, "chat") and origin.chat:
            return origin.chat.title
    if message.forward_from_chat:
        return message.forward_from_chat.title
    return None


# ─── Status formatting ────────────────────────────────────────────────────────

async def build_status_text(user_id: int) -> str:
    """Build status text for a specific user."""
    cfg = await load_config(user_id)
    state = await load_state(user_id)
    settings = await load_settings(user_id)

    source_line = (
        f"📢 <b>Source:</b> {cfg.source_title} (<code>{cfg.source_chat_id}</code>)"
        if cfg.is_source_configured()
        else "📢 <b>Source:</b> ❌ Not configured"
    )

    if cfg.is_destination_configured():
        if cfg.destination_type == "forum_topic":
            dest_line = (
                f"🗂 <b>Destination:</b> {cfg.destination_title} "
                f"(<code>{cfg.destination_chat_id}</code>)\n"
                f"   📌 <b>Topic thread ID:</b> <code>{cfg.destination_thread_id}</code>"
            )
        else:
            dest_line = (
                f"👥 <b>Destination:</b> {cfg.destination_title} "
                f"(<code>{cfg.destination_chat_id}</code>) [normal group]"
            )
    else:
        dest_line = "🗂 <b>Destination:</b> ❌ Not configured"

    if state.active:
        fwd_status = (
            f"⚙️ <b>Forwarding:</b> 🟢 Active\n"
            f"   Range: <code>{state.start_message_id}</code> → <code>{state.end_message_id}</code>\n"
            f"   Last processed: <code>{state.last_processed_message_id}</code>"
        )
    elif state.last_processed_message_id:
        fwd_status = (
            f"⚙️ <b>Forwarding:</b> ⏹ Stopped\n"
            f"   Last processed: <code>{state.last_processed_message_id}</code>"
        )
    else:
        fwd_status = "⚙️ <b>Forwarding:</b> ⏹ Idle"

    delay_line = f"⏱ <b>Delay:</b> {settings.delay_seconds}s per message"

    return "\n".join([source_line, dest_line, fwd_status, delay_line])


# ─── SetupSession helpers (anonymous-admin destination token bridge) ─────────
# Only used by the "Anonymous Admin Setup" path. Normal/Visible Setup keeps
# using set_topic_capture_mode()/is_topic_capture_active() above, unchanged.

_TOKEN_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # excludes 0/O/1/I/L
_TOKEN_LENGTH = 8


def generate_token() -> str:
    """Cryptographically secure 8-char token. Repeated characters allowed."""
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LENGTH))


async def create_session(user_id: int, mode: str, purpose: str = "destination") -> SetupSession:
    """
    Create a new setup session for the Anonymous Admin Setup flow.
    purpose: "destination" | "source" — kept isolated via explicit filtering
    in redeem_session, so a token created for one purpose can never resolve
    a request for the other.
    mode: "topic" | "normal_group"
    Does NOT invalidate other still-valid tokens the same user may hold.
    """
    now = datetime.now(timezone.utc)
    token = generate_token()
    session = SetupSession(
        token=token,
        user_id=user_id,
        purpose=purpose,
        mode=mode,
        created_at=now,
        expires_at=now + timedelta(seconds=config.TOPIC_CAPTURE_EXPIRY),
        used=False,
        pending=False,
    )
    await col_sessions().insert_one(session.to_dict())
    return session


async def redeem_session(
    token: str,
    mode: str,
    resolved_chat_id: int,
    resolved_title: Optional[str],
    resolved_thread_id: Optional[int],
    resolved_type: str,
    purpose: str = "destination",
) -> Optional[SetupSession]:
    """
    Atomically redeem a token: only succeeds once, only before expiry, only
    for the matching purpose (a "source" token can never satisfy a
    destination redemption and vice versa — this is checked in the same
    atomic filter, not after the fact), and only if the token's mode
    matches (a "topic" token cannot configure a normal_group destination
    and vice versa). On success the session moves into pending state,
    awaiting the owner's Confirm/Cancel in their private chat — nothing is
    saved to bot_config yet.

    Returns the updated session on success, or None if the token is
    invalid, expired, already used, wrong-purpose, or mode-mismatched —
    callers must use one generic rejection message for all of these to
    avoid leaking which condition failed.
    """
    now = datetime.now(timezone.utc)
    doc = await col_sessions().find_one_and_update(
        {
            "_id": token,
            "used": False,
            "expires_at": {"$gt": now},
            "purpose": purpose,
            "mode": mode,
        },
        {"$set": {
            "used": True,
            "pending": True,
            "resolved_chat_id": resolved_chat_id,
            "resolved_title": resolved_title,
            "resolved_thread_id": resolved_thread_id,
            "resolved_type": resolved_type,
        }},
        return_document=True,
    )
    if doc is None:
        return None
    return SetupSession.from_dict(doc)


async def get_pending_session(token: str) -> Optional[SetupSession]:
    """Fetch a redeemed-but-not-yet-confirmed session, for the Confirm/Cancel callbacks."""
    doc = await col_sessions().find_one({"_id": token, "pending": True})
    if doc is None:
        return None
    return SetupSession.from_dict(doc)


async def finalize_session(token: str) -> Optional[SetupSession]:
    """
    Atomically close out a pending session on Confirm (or Cancel — caller
    decides whether to act on the result). Idempotent: a second call (e.g.
    a double-tap on Confirm) finds pending already False and returns None,
    so the caller can safely no-op instead of saving twice.
    Still respects the original expires_at — no new timer is started for
    the confirmation step itself.
    """
    now = datetime.now(timezone.utc)
    doc = await col_sessions().find_one_and_update(
        {"_id": token, "pending": True, "expires_at": {"$gt": now}},
        {"$set": {"pending": False}},
        return_document=True,
    )
    if doc is None:
        return None
    return SetupSession.from_dict(doc)


# ─── Normal Group source: message link parsing + admin verification ──────────
# Only used by the Normal Group source feature. Channel source/range stay
# entirely forward-based (extract_forwarded_* above), untouched by this.

# Matches:
#   https://t.me/<public_username>/<message_id>
#   https://t.me/c/<internal_chat_id>/<message_id>
# Deliberately does NOT match 3-segment forum/topic-style links
# (https://t.me/<username_or_c/id>/<thread_id>/<message_id>) — those are
# out of scope for this feature and get a specific rejection message.
_GROUP_LINK_RE = re.compile(
    r"^https?://t\.me/(?:c/(\d+)|([a-zA-Z][\w]{4,31}))/(\d+)/?$"
)
_TOPIC_LINK_RE = re.compile(
    r"^https?://t\.me/(?:c/\d+|[a-zA-Z][\w]{4,31})/\d+/\d+/?$"
)


def is_topic_style_link(text: str) -> bool:
    """True if the text looks like a 3-segment forum/topic message link."""
    return bool(_TOPIC_LINK_RE.match((text or "").strip()))


def parse_group_message_link(text: str) -> Optional[tuple]:
    """
    Parse a Normal Group message link into (chat_id, message_id).
    For private links (t.me/c/<internal_id>/<msg>), chat_id is returned as
    the full -100-prefixed form Bot API expects.
    For public links (t.me/<username>/<msg>), chat_id is returned as the
    "@username" string — the caller must resolve it via bot.get_chat()
    before use, since Bot API needs a numeric chat_id or "@username" for
    lookups, not the bare username.
    Returns None if the text isn't a recognizable 2-segment group link.
    """
    text = (text or "").strip()
    m = _GROUP_LINK_RE.match(text)
    if not m:
        return None
    internal_id, username, message_id = m.groups()
    if internal_id:
        chat_id = int(f"-100{internal_id}")
        return chat_id, int(message_id)
    return f"@{username}", int(message_id)


async def resolve_group_chat_id(bot: Bot, chat_ref) -> Optional[int]:
    """
    Turn a chat_id or "@username" reference into a confirmed numeric
    chat_id, verifying the bot can actually see this chat (i.e. is at
    least a member — required for get_chat to succeed at all).
    """
    try:
        chat = await bot.get_chat(chat_ref)
        return chat.id
    except Exception as e:
        logger.warning("resolve_group_chat_id failed for %s: %s", chat_ref, e)
        return None


async def bot_is_admin_in_chat(bot: Bot, chat_id: int) -> bool:
    """
    Verify the bot has admin status in the given chat. Used at Normal Group
    source setup time (not only discovered later when forwarding fails).
    """
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.warning("bot_is_admin_in_chat failed for chat_id=%s: %s", chat_id, e)
        return False
