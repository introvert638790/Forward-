import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import config

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """Initialize MongoDB connection."""
    global _client, _db
    try:
        _client = AsyncIOMotorClient(config.MONGO_URI)
        _db = _client[config.MONGO_DB_NAME]
        # Verify connection
        await _client.admin.command("ping")
        # TTL index for anonymous-admin setup tokens: cleanup only.
        # Real expiry authorization check happens explicitly in
        # utils/helpers.redeem_session() — this index is NOT relied upon
        # for auth correctness, only for eventually removing stale docs.
        await _db["setup_sessions"].create_index("expires_at", expireAfterSeconds=0)
        logger.info("MongoDB connected successfully.")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise


async def close_db() -> None:
    """Close MongoDB connection."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """Return the active database instance."""
    if _db is None:
        raise RuntimeError("Database is not connected. Call connect_db() first.")
    return _db


# ─── Collection accessors ─────────────────────────────────────────────────────

def col_config():
    """bot_config: per-user source + destination configuration."""
    return get_db()["bot_config"]


def col_state():
    """forwarding_state: per-user active task progress and stop flag."""
    return get_db()["forwarding_state"]


def col_settings():
    """bot_settings: per-user delay, topic capture mode, etc."""
    return get_db()["bot_settings"]


def col_users():
    """
    users: user profiles, access status, usage statistics.
    NEW in multi-user version.
    """
    return get_db()["users"]


def col_sessions():
    """
    setup_sessions: temporary tokens bridging an anonymous-admin
    /setdestination message back to the real private-chat user_id
    that generated the token. TTL-indexed on expires_at for cleanup.
    """
    return get_db()["setup_sessions"]
