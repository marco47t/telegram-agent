# Telegram Agent MVP

Routes messages by complexity: trivial -> canned reply, simple -> Flash-Lite,
complex -> Antigravity (rotating across two Google accounts). Remembers
durable facts about you via Postgres + local-embedding ChromaDB. Handles
basic reminders.

## Setup

1. **Postgres**
   ```bash
   createdb agent_db
   psql agent_db -f sql/schema.sql
   ```

2. **Python env**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Env vars**
   ```bash
   cp .env.example .env
   # fill in TELEGRAM_BOT_TOKEN (from @BotFather), GEMINI_API_KEY (from AI Studio),
   # DATABASE_URL, and the two ANTIGRAVITY_HOME_* paths.
   ```

4. **Antigravity accounts**
   Each account needs its own cached-credential directory so the bot can
   rotate between them. For each account:
   ```bash
   mkdir -p /home/agent/.antigravity-a
   HOME=/home/agent/.antigravity-a agy
   # sign in interactively once, then exit
   ```
   Repeat for `.antigravity-b` with your second account.

5. **First run**
   ```bash
   python3 bot.py
   ```

## What happens on first message

1. Message logged to Postgres immediately.
2. Trivial patterns (greetings/thanks/farewells) get a canned reply, no
   model call.
3. "remind me..." gets parsed into a due_at timestamp via Flash-Lite and
   stored; the scheduler polls every 60s and pushes it back via Telegram.
4. Everything else gets classified simple/complex, relevant memories are
   retrieved from ChromaDB and injected into the prompt, then routed to
   Flash-Lite or Antigravity accordingly.
5. Every 10 undistilled messages, a background pass extracts durable facts
   and stores them as embeddings for future retrieval.

## Known gaps (by design, for a v2)

- No `--dangerously-skip-permissions` review process yet -- fine for a
  personal single-user bot, revisit before giving it filesystem/shell tools.
- Reminder parsing has no timezone handling beyond UTC; add per-user
  timezone once `users.timezone` is actually used.
- No retry/backoff on Gemini API calls -- add if you hit transient errors.
- Web search tool not wired in yet (next step).
