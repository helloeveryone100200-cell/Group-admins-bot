"""
ARQ background task definitions.

Executed in a separate worker process so the Telegram bot handler loop
remains free during long operations (broadcast to 1000+ groups, etc.).

Each task receives `ctx` (the ARQ context dict) which holds:
  ctx["bot"]  — telegram.Bot instance (created in WorkerSettings.on_startup)
"""
from __future__ import annotations
import asyncio
import logging

from telegram import Bot
from helpers.formatting import header

log = logging.getLogger(__name__)

_FLOOD_DELAY = 0.05   # seconds between bulk sends (Telegram rate-limit)


async def broadcast_all(
    ctx: dict,
    *,
    text: str,
    admin_id: int,
    parse_mode: str = "HTML",
) -> None:
    """Send `text` to every registered group, then DM a summary to admin."""
    import database as db   # local import avoids Motor init at module load
    bot: Bot = ctx["bot"]
    groups = await db.get_all_groups()
    sent, failed = 0, 0
    for g in groups:
        try:
            await bot.send_message(
                g["chat_id"],
                f"{header('📢 Broadcast')}\n\n{text}",
                parse_mode=parse_mode,
            )
            sent += 1
        except Exception as exc:
            log.debug("broadcast_all skip %s: %s", g.get("chat_id"), exc)
            failed += 1
        await asyncio.sleep(_FLOOD_DELAY)
    try:
        await bot.send_message(
            admin_id,
            (
                f"📢 <b>Broadcast complete.</b>\n"
                f"Sent: <b>{sent}</b>  Failed: <b>{failed}</b>"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def broadcast_group(
    ctx: dict,
    *,
    text: str,
    chat_id: int,
    admin_id: int,
    parse_mode: str = "HTML",
) -> None:
    """Send `text` to a single group."""
    bot: Bot = ctx["bot"]
    try:
        await bot.send_message(
            chat_id,
            f"{header('📢 Broadcast')}\n\n{text}",
            parse_mode=parse_mode,
        )
        await bot.send_message(
            admin_id, "✅ Group broadcast sent.", parse_mode="HTML"
        )
    except Exception as exc:
        try:
            await bot.send_message(
                admin_id, f"❌ Failed: {exc}", parse_mode="HTML"
            )
        except Exception:
            pass


async def broadcast_user(
    ctx: dict,
    *,
    text: str,
    target_user_id: int,
    admin_id: int,
    parse_mode: str = "HTML",
) -> None:
    """Send `text` to a single user."""
    bot: Bot = ctx["bot"]
    try:
        await bot.send_message(target_user_id, text, parse_mode=parse_mode)
        await bot.send_message(
            admin_id, "✅ User broadcast sent.", parse_mode="HTML"
        )
    except Exception as exc:
        try:
            await bot.send_message(
                admin_id, f"❌ Failed: {exc}", parse_mode="HTML"
            )
        except Exception:
            pass
