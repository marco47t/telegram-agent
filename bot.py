"""
Main entrypoint. Wires: Telegram <-> router <-> (Flash-Lite | Antigravity)
<-> Postgres (history) + ChromaDB (semantic memory) <-> reminders.
"""
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters

import db
import memory
import llm
import router
import reminders

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

MEMORY_TOP_K = int(os.environ.get("MEMORY_TOP_K", 5))
MEMORY_THRESHOLD = float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", 0.5))
DISTILL_EVERY_N_MESSAGES = 10


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    telegram_user = update.effective_user

    user_id = await db.get_or_create_user(telegram_user.id, telegram_user.full_name)
    conversation_id = await db.get_or_create_active_conversation(user_id)
    await db.log_message(conversation_id, user_id, "user", text)

    # 1. Trivial -> canned response, no model call at all
    trivial_key = router.classify_trivial(text)
    if trivial_key:
        reply = router.TRIVIAL_RESPONSES[trivial_key]
        await update.message.reply_text(reply)
        await db.log_message(conversation_id, user_id, "assistant", reply, route="trivial")
        return

    # 2. Reminder command
    if text.lower().startswith("remind me") or text.startswith("/remind"):
        parsed = await reminders.parse_reminder_request(text)
        if parsed:
            due_at = datetime.fromisoformat(parsed["due_at"])
            await db.create_reminder(user_id, parsed["text"], due_at)
            reply = f"Got it -- I'll remind you: \"{parsed['text']}\" at {due_at.strftime('%Y-%m-%d %H:%M UTC')}."
        else:
            reply = "Couldn't work out the time on that one -- try something like \"remind me to call mom tomorrow at 6pm\"."
        await update.message.reply_text(reply)
        await db.log_message(conversation_id, user_id, "assistant", reply, route="trivial")
        return

    # 3. Simple vs complex routing
    route = await llm.classify_route(text)

    # Pull relevant memory context for anything non-trivial
    memories = memory.retrieve_memories(user_id, text, k=MEMORY_TOP_K, similarity_threshold=MEMORY_THRESHOLD)
    context_block = ""
    if memories:
        context_block = "\n\nThings you know about this user:\n" + "\n".join(f"- {m}" for m in memories)

    prompt = f"{text}{context_block}"

    if route == "complex":
        reply = await llm.call_antigravity(prompt)
    else:
        reply = await llm.call_flash_lite(prompt)

    await update.message.reply_text(reply)
    await db.log_message(conversation_id, user_id, "assistant", reply, route=route)

    # 4. Periodically distill recent history into long-term memory
    undistilled = await db.get_undistilled_messages(user_id, min_count=DISTILL_EVERY_N_MESSAGES)
    if undistilled:
        facts = await llm.distill_memories(undistilled)
        for fact in facts:
            vector_id = memory.store_memory(user_id, fact["content"], fact["category"])
            await db.save_memory_entry(user_id, fact["content"], fact["category"], vector_id)
        await db.mark_distilled([m["id"] for m in undistilled])
        log.info("Distilled %d facts from %d messages for user %d", len(facts), len(undistilled), user_id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Online. What do you need?")


async def post_init(application: Application):
    await db.init_pool()
    memory.init_memory()
    reminders.start_reminder_scheduler(application.bot)
    log.info("Startup complete: Postgres pool, ChromaDB, and reminder scheduler are live.")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
