"""
Shared utilities — auto-delete helper, time parsing, etc.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Message

log = logging.getLogger(__name__)

AUTO_DELETE_DELAY = 300  # 5 minutes


async def _delete_later(msg: Message, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass  # already deleted or no permission


async def send_and_delete(
    message: Message,
    text: str,
    delay: int = AUTO_DELETE_DELAY,
    **kwargs,
) -> Message:
    """
    Reply with `text` and auto-delete both the bot reply and the
    triggering user message after `delay` seconds (default 5 min).
    """
    sent = await message.reply_text(text, **kwargs)
    asyncio.create_task(_delete_later(sent, delay))
    asyncio.create_task(_delete_later(message, delay))
    return sent


def parse_time(time_str: str) -> tuple[int, int] | None:
    """
    Parse 'HH:MM' → (hour, minute). Returns None on error.
    """
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M")
        return t.hour, t.minute
    except ValueError:
        return None


def parse_datetime(dt_str: str) -> datetime | None:
    """
    Parse 'YYYY-MM-DD HH:MM' → datetime. Returns None on error.
    """
    for fmt in ("%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    return None


def seconds_until(hour: int, minute: int) -> float:
    """Seconds until next occurrence of HH:MM (tomorrow if already past)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()
