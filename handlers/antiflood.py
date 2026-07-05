"""
Anti-flood protection.
All bot command replies auto-delete after 5 minutes.
"""
from __future__ import annotations
import time
from collections import defaultdict, deque
from telegram import Update, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, mono, mention, error, success, header, italic
from helpers.utils import send_and_delete

# In-memory flood tracker: {(chat_id, user_id): deque of timestamps}
_tracker: dict[tuple[int, int], deque] = defaultdict(deque)


# ── /antiflood ────────────────────────────────────────────────────────────────

@admin_only
async def antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if not args:
        limit = await db.get_flood_limit(chat.id)
        mode = await db.get_flood_mode(chat.id)
        status = bold("ENABLED") if limit > 0 else bold("DISABLED")
        await send_and_delete(
            msg,
            f"{header('Anti-Flood')}\n\n"
            f"{bold('Status:')} {status}\n"
            f"{bold('Limit:')} {mono(str(limit) if limit else 'Off')}\n"
            f"{bold('Action:')} {mono(mode)}\n\n"
            f"{italic('Usage:')} /antiflood &lt;number&gt;  {italic('(0 = disable)')}",
            parse_mode=ParseMode.HTML,
        )
        return
    if not args[0].isdigit():
        await send_and_delete(
            msg, error("Please provide a number."), parse_mode=ParseMode.HTML
        )
        return
    limit = int(args[0])
    await db.set_flood_limit(chat.id, limit)
    if limit == 0:
        await send_and_delete(
            msg,
            success("Anti-flood has been disabled."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await send_and_delete(
            msg,
            success(f"Anti-flood set to {bold(str(limit))} messages per 10 seconds."),
            parse_mode=ParseMode.HTML,
        )


# ── /floodmode ────────────────────────────────────────────────────────────────

@admin_only
async def floodmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    modes = ["ban", "kick", "mute", "warn"]
    if not args or args[0].lower() not in modes:
        current = await db.get_flood_mode(chat.id)
        opts = " | ".join(mono(m) for m in modes)
        await send_and_delete(
            msg,
            f"{header('Flood Mode')}\n\n"
            f"{bold('Current:')} {mono(current)}\n"
            f"{italic('Options:')} {opts}\n"
            f"{italic('Usage:')} /floodmode &lt;mode&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    mode = args[0].lower()
    await db.set_flood_mode(chat.id, mode)
    await send_and_delete(
        msg,
        success(f"Flood action set to {bold(mode)}."),
        parse_mode=ParseMode.HTML,
    )


# ── Message watcher ───────────────────────────────────────────────────────────

async def flood_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not user or not chat or not msg:
        return

    # exempt admins
    member = await chat.get_member(user.id)
    if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
        return

    limit = await db.get_flood_limit(chat.id)
    if limit == 0:
        return

    key = (chat.id, user.id)
    now = time.time()
    dq = _tracker[key]
    dq.append(now)
    # keep only messages within 10 seconds
    while dq and now - dq[0] > 10:
        dq.popleft()

    if len(dq) < limit:
        return

    # flooder detected — clear tracker
    _tracker.pop(key, None)
    mode = await db.get_flood_mode(chat.id)

    try:
        await msg.delete()
    except Exception:
        pass

    from handlers.admin import MUTE_PERMS
    name = mention(user.full_name, user.id)
    if mode == "ban":
        await chat.ban_member(user.id)
        text = f"{name} has been {bold('banned')} for flooding."
    elif mode == "kick":
        await chat.ban_member(user.id)
        await chat.unban_member(user.id)
        text = f"{name} has been {bold('kicked')} for flooding."
    elif mode == "mute":
        await chat.restrict_member(user.id, MUTE_PERMS)
        text = f"{name} has been {bold('muted')} for flooding."
    else:  # warn
        count = await db.add_warn(chat.id, user.id, "Flooding")
        limit_w = await db.get_warn_limit(chat.id)
        text = (
            f"{name} warned for flooding. "
            f"{bold(f'{count}/{limit_w}')} warnings."
        )
        if count >= limit_w:
            await chat.ban_member(user.id)
            text += f"\n{bold('⛔ Auto-banned — warn limit reached!')}"

    await chat.send_message(text, parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("antiflood", antiflood))
    app.add_handler(CommandHandler("floodmode", floodmode))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, flood_watch), group=5
    )
