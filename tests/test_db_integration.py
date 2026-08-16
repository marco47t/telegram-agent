import pytest
import pytest_asyncio
import os
import db
from datetime import datetime, timezone, timedelta

# Skip all tests in this file if DATABASE_URL is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set"
)

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    # Attempt to initialize connection pool
    try:
        pool = await db.init_pool()

        # In a real integration test, you might want to truncate tables here to ensure clean state
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE users, conversations, messages, memory_entries, reminders CASCADE;")

        yield
    finally:
        await db.close_pool()

@pytest.mark.asyncio
async def test_get_or_create_user():
    user_id_1 = await db.get_or_create_user(12345, "Test User")
    assert user_id_1 is not None

    # Second time should return the same ID
    user_id_2 = await db.get_or_create_user(12345, "Test User")
    assert user_id_1 == user_id_2

    # Different telegram ID should return a different ID
    user_id_3 = await db.get_or_create_user(67890, "Another User")
    assert user_id_1 != user_id_3

@pytest.mark.asyncio
async def test_log_message():
    user_id = await db.get_or_create_user(111, "Log User")
    conv_id = await db.get_or_create_active_conversation(user_id)

    msg_id = await db.log_message(conv_id, user_id, "user", "Hello DB", route="simple")
    assert msg_id is not None

    # Verify retrieval
    recent = await db.get_recent_messages(conv_id, limit=5)
    assert len(recent) == 1
    assert recent[0]["role"] == "user"
    assert recent[0]["content"] == "Hello DB"

@pytest.mark.asyncio
async def test_reminders():
    user_id = await db.get_or_create_user(222, "Reminder User")

    # Create reminder due in the past
    past_due = datetime.now(timezone.utc) - timedelta(minutes=5)
    reminder_id = await db.create_reminder(user_id, "Test Reminder", past_due)
    assert reminder_id is not None

    # Fetch due reminders
    due = await db.get_due_reminders()
    assert any(r["id"] == reminder_id for r in due)
    assert any(r["text"] == "Test Reminder" for r in due)

    # Mark sent
    await db.mark_reminder_sent(reminder_id)

    # Fetch again, should not be pending
    due_after = await db.get_due_reminders()
    assert not any(r["id"] == reminder_id for r in due_after)
