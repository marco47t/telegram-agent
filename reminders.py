"""
Polls Postgres for due reminders and pushes them via the bot. Also parses
natural-language reminder requests using Flash-Lite (cheap enough to use
for every "remind me to..." without worrying about cost).
"""
import json
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import db
import llm


async def check_due_reminders(bot):
    due = await db.get_due_reminders()
    for reminder in due:
        try:
            await bot.send_message(chat_id=reminder["telegram_id"], text=f"Reminder: {reminder['text']}")
        finally:
            await db.mark_reminder_sent(reminder["id"])


def start_reminder_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_due_reminders, "interval", seconds=60, args=[bot])
    scheduler.start()
    return scheduler


async def parse_reminder_request(text: str) -> dict | None:
    """
    Takes something like "remind me to call mom tomorrow at 6pm" and returns
    {"text": "call mom", "due_at": "2026-08-17T18:00:00"} or None if it
    couldn't be parsed. Current time is passed in so "tomorrow"/"in 2 hours"
    resolve correctly.
    """
    now = datetime.now(timezone.utc).isoformat()
    prompt = f"""Current UTC time: {now}
Parse this reminder request into JSON: {{"text": "...", "due_at": "ISO-8601 UTC timestamp"}}
If it can't be parsed as a reminder, return {{"text": null, "due_at": null}}.
Respond with raw JSON only, no markdown fences.

Request: {text}"""

    raw = await llm.call_flash_lite(prompt, system="You extract structured reminder data. Output raw JSON only.")
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(raw)
        if not parsed.get("text") or not parsed.get("due_at"):
            return None
        return parsed
    except (json.JSONDecodeError, KeyError):
        return None
