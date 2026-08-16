"""
Thin async Postgres access layer. One connection pool shared across the app.
"""
import os
from datetime import datetime
import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"], min_size=1, max_size=10)
    return _pool


async def close_pool():
    if _pool:
        await _pool.close()


async def get_or_create_user(telegram_id: int, name: str | None) -> int:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE telegram_id = $1", telegram_id)
        if row:
            return row["id"]
        row = await conn.fetchrow(
            "INSERT INTO users (telegram_id, name) VALUES ($1, $2) RETURNING id",
            telegram_id, name,
        )
        return row["id"]


async def get_or_create_active_conversation(user_id: int) -> int:
    """
    Reuses the most recent conversation if it's been active in the last
    2 hours, otherwise starts a new one. Keeps conversation boundaries
    roughly aligned with actual chat sessions instead of one giant thread.
    """
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM conversations
            WHERE user_id = $1 AND last_active_at > now() - interval '2 hours'
            ORDER BY last_active_at DESC LIMIT 1
            """,
            user_id,
        )
        if row:
            await conn.execute(
                "UPDATE conversations SET last_active_at = now() WHERE id = $1", row["id"]
            )
            return row["id"]
        row = await conn.fetchrow(
            "INSERT INTO conversations (user_id) VALUES ($1) RETURNING id", user_id
        )
        return row["id"]


async def log_message(conversation_id: int, user_id: int, role: str, content: str, route: str | None = None) -> int:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages (conversation_id, user_id, role, content, route)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
            """,
            conversation_id, user_id, role, content, route,
        )
        return row["id"]


async def get_recent_messages(conversation_id: int, limit: int = 20) -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, created_at FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            conversation_id, limit,
        )
        return [dict(r) for r in reversed(rows)]


async def get_undistilled_messages(user_id: int, min_count: int = 10) -> list[dict] | None:
    """Returns undistilled messages for a user if there are at least min_count of them."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, role, content FROM messages
            WHERE user_id = $1 AND distilled = FALSE
            ORDER BY created_at ASC
            """,
            user_id,
        )
        if len(rows) < min_count:
            return None
        return [dict(r) for r in rows]


async def mark_distilled(message_ids: list[int]):
    async with _pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET distilled = TRUE WHERE id = ANY($1::bigint[])", message_ids
        )


async def save_memory_entry(user_id: int, content: str, category: str, vector_id: str) -> int:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memory_entries (user_id, content, category, vector_id)
            VALUES ($1, $2, $3, $4) RETURNING id
            """,
            user_id, content, category, vector_id,
        )
        return row["id"]


async def create_reminder(user_id: int, text: str, due_at: datetime) -> int:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO reminders (user_id, text, due_at) VALUES ($1, $2, $3) RETURNING id",
            user_id, text, due_at,
        )
        return row["id"]


async def get_due_reminders() -> list[dict]:
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.text, u.telegram_id
            FROM reminders r JOIN users u ON u.id = r.user_id
            WHERE r.status = 'pending' AND r.due_at <= now()
            """
        )
        return [dict(r) for r in rows]


async def mark_reminder_sent(reminder_id: int):
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE reminders SET status = 'sent' WHERE id = $1", reminder_id)
