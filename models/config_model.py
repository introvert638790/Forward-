from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class BotConfig:
    """
    Stored in collection: bot_config
    Keyed by user_id (_id = user_id) instead of singleton.
    Each user has their own isolated source + destination config.
    """
    user_id: int = 0                          # NEW: per-user isolation key

    source_chat_id: Optional[int] = None
    source_title: Optional[str] = None
    # "channel" | "normal_group" — defaults to "channel" for backward
    # compatibility with configs saved before this field existed.
    source_type: Optional[str] = None

    destination_chat_id: Optional[int] = None
    destination_title: Optional[str] = None

    # "forum_topic" | "normal_group" | "forum_general"
    destination_type: Optional[str] = None

    # Only set when destination_type == "forum_topic"
    destination_thread_id: Optional[int] = None

    def is_source_configured(self) -> bool:
        return self.source_chat_id is not None

    def is_destination_configured(self) -> bool:
        return self.destination_chat_id is not None

    def is_fully_configured(self) -> bool:
        return self.is_source_configured() and self.is_destination_configured()

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "source_chat_id": self.source_chat_id,
            "source_title": self.source_title,
            "source_type": self.source_type,
            "destination_chat_id": self.destination_chat_id,
            "destination_title": self.destination_title,
            "destination_type": self.destination_type,
            "destination_thread_id": self.destination_thread_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BotConfig":
        return cls(
            user_id=d.get("user_id", 0),
            source_chat_id=d.get("source_chat_id"),
            source_title=d.get("source_title"),
            source_type=d.get("source_type") or ("channel" if d.get("source_chat_id") else None),
            destination_chat_id=d.get("destination_chat_id"),
            destination_title=d.get("destination_title"),
            destination_type=d.get("destination_type"),
            destination_thread_id=d.get("destination_thread_id"),
        )


@dataclass
class ForwardingState:
    """
    Stored in collection: forwarding_state
    Keyed by user_id (_id = user_id) instead of singleton.
    Each user has their own isolated forwarding progress.
    """
    user_id: int = 0                          # NEW: per-user isolation key

    active: bool = False
    stop_flag: bool = False
    start_message_id: Optional[int] = None
    end_message_id: Optional[int] = None
    last_processed_message_id: Optional[int] = None

    # ── Phase 1: Auto Resume / recovery fields ─────────────────────────────
    # status: "idle" | "forwarding" | "recovering" | "cancelled" | "failed" | "completed"
    status: str = "idle"
    cancelled: bool = False                   # True only for intentional user Stop
    failed_count: int = 0
    skipped_count: int = 0
    completion_sent: bool = False              # Phase 2: guards duplicate "That's it ♥️"

    # ── Phase 2: Auto Pin ───────────────────────────────────────────────────
    pinned_done: bool = False

    # ── Phase 3: Single editable progress message ──────────────────────────
    progress_message_id: Optional[int] = None
    progress_chat_id: Optional[int] = None
    job_started_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "active": self.active,
            "stop_flag": self.stop_flag,
            "start_message_id": self.start_message_id,
            "end_message_id": self.end_message_id,
            "last_processed_message_id": self.last_processed_message_id,
            "status": self.status,
            "cancelled": self.cancelled,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "completion_sent": self.completion_sent,
            "pinned_done": self.pinned_done,
            "progress_message_id": self.progress_message_id,
            "progress_chat_id": self.progress_chat_id,
            "job_started_at": self.job_started_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ForwardingState":
        return cls(
            user_id=d.get("user_id", 0),
            active=d.get("active", False),
            stop_flag=d.get("stop_flag", False),
            start_message_id=d.get("start_message_id"),
            end_message_id=d.get("end_message_id"),
            last_processed_message_id=d.get("last_processed_message_id"),
            status=d.get("status", "idle"),
            cancelled=d.get("cancelled", False),
            failed_count=d.get("failed_count", 0),
            skipped_count=d.get("skipped_count", 0),
            completion_sent=d.get("completion_sent", False),
            pinned_done=d.get("pinned_done", False),
            progress_message_id=d.get("progress_message_id"),
            progress_chat_id=d.get("progress_chat_id"),
            job_started_at=d.get("job_started_at"),
        )


@dataclass
class BotSettings:
    """
    Stored in collection: bot_settings
    Keyed by user_id (_id = user_id) instead of singleton.
    Each user has their own delay and capture mode flag.
    """
    user_id: int = 0                          # NEW: per-user isolation key

    delay_seconds: float = 3.0
    topic_capture_mode: bool = False
    topic_capture_expires: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "delay_seconds": self.delay_seconds,
            "topic_capture_mode": self.topic_capture_mode,
            "topic_capture_expires": self.topic_capture_expires,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BotSettings":
        return cls(
            user_id=d.get("user_id", 0),
            delay_seconds=d.get("delay_seconds", 3.0),
            topic_capture_mode=d.get("topic_capture_mode", False),
            topic_capture_expires=d.get("topic_capture_expires"),
        )


# ─── NEW: SetupSession (anonymous-admin destination token bridge) ────────────

@dataclass
class SetupSession:
    """
    Stored in collection: setup_sessions
    Keyed by the token itself (_id = token). Only used for the Anonymous
    Admin Setup path — Normal/Visible Setup never creates one of these.

    Lifecycle: created (pending=False, used=False)
             -> redeemed (used=True, pending=True, resolved_* filled)
             -> confirmed (pending=False, destination saved) or cancelled.

    purpose values: "destination" | "source" — keeps the two token
    families completely isolated from each other even though they share
    one collection; redemption always filters on purpose explicitly, so
    a source token can never resolve a destination request or vice versa.
    mode values: "topic" | "normal_group" (meaning depends on purpose:
    for purpose="source", mode is always "normal_group" since Channel
    source setup never uses tokens).
    """
    token: str = ""
    user_id: int = 0
    purpose: str = "destination"
    mode: str = "normal_group"

    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    used: bool = False                        # True once atomically redeemed
    pending: bool = False                      # True while awaiting Confirm/Cancel

    resolved_chat_id: Optional[int] = None
    resolved_title: Optional[str] = None
    resolved_thread_id: Optional[int] = None
    resolved_type: Optional[str] = None        # "normal_group" | "forum_topic" | "forum_general"

    def to_dict(self) -> dict:
        return {
            "_id": self.token,
            "user_id": self.user_id,
            "purpose": self.purpose,
            "mode": self.mode,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "used": self.used,
            "pending": self.pending,
            "resolved_chat_id": self.resolved_chat_id,
            "resolved_title": self.resolved_title,
            "resolved_thread_id": self.resolved_thread_id,
            "resolved_type": self.resolved_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SetupSession":
        return cls(
            token=d.get("_id", ""),
            user_id=d.get("user_id", 0),
            purpose=d.get("purpose", "destination"),
            mode=d.get("mode", "normal_group"),
            created_at=d.get("created_at"),
            expires_at=d.get("expires_at"),
            used=d.get("used", False),
            pending=d.get("pending", False),
            resolved_chat_id=d.get("resolved_chat_id"),
            resolved_title=d.get("resolved_title"),
            resolved_thread_id=d.get("resolved_thread_id"),
            resolved_type=d.get("resolved_type"),
        )


# ─── NEW: UserProfile ─────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """
    Stored in collection: users
    Keyed by user_id (_id = user_id).
    Tracks identity, access status, and basic usage statistics.

    status values:
      "allowed"  — can use forwarding features
      "banned"   — access denied
      "pending"  — unknown user, awaiting owner approval
    """
    user_id: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None

    status: str = "pending"                   # "allowed" | "banned" | "pending"

    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    usage_count: int = 0

    def is_allowed(self) -> bool:
        return self.status == "allowed"

    def is_banned(self) -> bool:
        return self.status == "banned"

    def is_pending(self) -> bool:
        return self.status == "pending"

    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.first_name or str(self.user_id)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "usage_count": self.usage_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UserProfile":
        return cls(
            user_id=d.get("user_id", 0),
            username=d.get("username"),
            first_name=d.get("first_name"),
            status=d.get("status", "pending"),
            first_seen=d.get("first_seen"),
            last_seen=d.get("last_seen"),
            usage_count=d.get("usage_count", 0),
        )
