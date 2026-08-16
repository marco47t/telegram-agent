"""
Model access layer.

- Flash-Lite: called directly via the Gemini API (cheap/free, used for
  routing, simple replies, and memory distillation).
- Antigravity: called via the `agy` CLI in headless (-p) mode, since it
  doesn't expose a plain HTTP API. We rotate between two Google accounts
  by pointing HOME at two separate cached-credential directories.
"""
import asyncio
import json
import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_flash_lite = genai.GenerativeModel("gemini-3.5-flash-lite")

PERSONALITY_PROMPT = """You are a witty, capable personal assistant in the vein of \
Jarvis/Edith -- calm, dry humor, competent, never fawning. Keep replies concise \
unless the user is asking for something detailed. Narrate briefly when doing \
multi-step work ("checking that now...") rather than going silent."""

ANTIGRAVITY_ACCOUNTS = [
    os.environ.get("ANTIGRAVITY_HOME_ACCOUNT_A"),
    os.environ.get("ANTIGRAVITY_HOME_ACCOUNT_B"),
]


async def call_flash_lite(prompt: str, system: str = PERSONALITY_PROMPT) -> str:
    full_prompt = f"{system}\n\nUser: {prompt}"
    response = await asyncio.to_thread(_flash_lite.generate_content, full_prompt)
    return response.text.strip()


async def _run_agy(prompt: str, home_dir: str, timeout: int = 120) -> tuple[bool, str]:
    """
    Runs one headless Antigravity call under a given credential HOME.
    Returns (success, output_or_error).
    """
    env = os.environ.copy()
    env["HOME"] = home_dir

    proc = await asyncio.create_subprocess_exec(
        "agy", "-p", prompt, "--output-format", "json", "--dangerously-skip-permissions",
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "timeout"

    if proc.returncode != 0:
        return False, stderr.decode(errors="ignore")

    try:
        payload = json.loads(stdout.decode())
        return True, payload.get("result") or payload.get("text", "")
    except json.JSONDecodeError:
        return False, "bad_json_output"


async def call_antigravity(prompt: str, system: str = PERSONALITY_PROMPT) -> str:
    """
    Tries each configured Google account in order. If every account is out
    of quota (or agy isn't set up), falls back to Flash-Lite with a note --
    better a degraded answer than no answer.
    """
    full_prompt = f"{system}\n\n{prompt}"

    for home_dir in ANTIGRAVITY_ACCOUNTS:
        if not home_dir:
            continue
        success, output = await _run_agy(full_prompt, home_dir)
        if success:
            return output
        is_quota_error = "quota" in output.lower() or "rate limit" in output.lower()
        if not is_quota_error:
            # A real error (auth, crash, etc) -- don't silently burn the other account too.
            break

    fallback = await call_flash_lite(
        f"(Note: complex-task routing was unavailable, answer as best you can)\n{prompt}",
        system=system,
    )
    return fallback


async def classify_route(message: str) -> str:
    """Returns 'simple' or 'complex'. Trivial messages are filtered before this is called."""
    prompt = (
        "Classify this message as exactly one word, 'simple' or 'complex'. "
        "'simple' = quick factual question, short rewrite, casual chat. "
        "'complex' = coding, multi-step reasoning, planning, research.\n\n"
        f"Message: {message}\n\nAnswer with one word only."
    )
    result = await call_flash_lite(prompt, system="You are a classifier. Respond with exactly one word.")
    result = result.strip().lower()
    return "complex" if "complex" in result else "simple"


async def distill_memories(messages: list[dict]) -> list[dict]:
    """
    Given a batch of raw messages, extracts durable facts worth remembering.
    Returns a list of {"content": str, "category": str} or [] if nothing's worth keeping.
    """
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    prompt = f"""Extract any durable facts, preferences, or context about the user worth \
remembering long-term from this conversation snippet. Ignore small talk, one-off \
questions, and anything not worth recalling later.

Respond ONLY with a JSON array (no markdown fences), each item shaped like:
{{"content": "user's dog is named Rex", "category": "fact"}}
category must be one of: preference, fact, event, project_context
Return [] if nothing is worth storing.

Transcript:
{transcript}"""

    raw = await call_flash_lite(prompt, system="You extract structured memory facts. Output raw JSON only.")
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        items = json.loads(raw)
        return items if isinstance(items, list) else []
    except json.JSONDecodeError:
        return []
