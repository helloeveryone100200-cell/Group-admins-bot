"""
Lock / unlock chat permissions.
Saves state to DB and actually applies set_permissions() to the chat.
"""
from __future__ import annotations
import asyncio
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import error, success, bold, mono, header, italic
from helpers.utils import send_and_delete, _delete_later

# Maps lock-type name → ChatPermissions field name
LOCK_TYPES = {
    "messages":  "can_send_messages",
    "media":     "can_send_other_messages",
    "stickers":  "can_send_other_messages",
    "gifs":      "can_send_other_messages",
    "polls":     "can_send_polls",
    "invite":    "can_invite_users",
    "pin":       "can_pin_messages",
    "info":      "can_change_info",
    "webprev":   "can_add_web_page_previews",
    "audios":    "can_send_audios",
    "docs":      "can_send_documents",
    "photos":    "can_send_photos",
    "videos":    "can_send_videos",
}

_PERM_FIELDS = [
    "can_send_messages",
    "can_send_audios",
    "can_send_documents",
    "can_send_photos",
    "can_send_videos",
    "can_send_video_notes",
    "can_send_voice_notes",
    "can_send_polls",
    "can_send_other_messages",
    "can_add_web_page_previews",
    "can_change_info",
    "can_invite_users",
    "can_pin_messages",
]

ALL_ON = ChatPermissions(
    can_send_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
    can_pin_messages=False,
    can_change_info=False,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
)

ALL_OFF = ChatPermissions(
    can_send_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_invite_users=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
)


async def _set_one_perm(bot, chat_id: int, perm_key: str, value: bool) -> None:
    """Read current chat permissions, flip one field, then apply."""
    chat_obj = await bot.get_chat(chat_id)
    perms = chat_obj.permissions or ChatPermissions()
    kwargs = {f: getattr(perms, f, None) for f in _PERM_FIELDS}
    kwargs[perm_key] = value
    await bot.set_chat_permissions(chat_id, ChatPermissions(**kwargs))


# ── /lock ─────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    chat = update.effective_chat
    msg = update.effective_message

    if not args:
        types = "\n".join(f"  • {mono(t)}" for t in sorted(set(LOCK_TYPES)))
        await send_and_delete(
            msg,
            f"{header('Lock Types')}\n\n{types}\n\n{italic('Example:')} {mono('/lock messages')}",
            parse_mode=ParseMode.HTML,
        )
        return

    lock_type = args[0].lower()
    if lock_type not in LOCK_TYPES and lock_type != "all":
        await send_and_delete(
            msg,
            error(f"Unknown lock type: {mono(lock_type)}\nUse /locktypes to see all."),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        if lock_type == "all":
            await chat.set_permissions(ALL_OFF)
        else:
            perm_key = LOCK_TYPES[lock_type]
            await _set_one_perm(context.bot, chat.id, perm_key, False)
            await db.set_lock(chat.id, lock_type, True)

        await send_and_delete(
            msg,
            success(f"{bold(lock_type.title())} locked for all members."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /unlock ───────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    chat = update.effective_chat
    msg = update.effective_message

    if not args:
        await send_and_delete(
            msg,
            error("Usage: /unlock <type> — e.g. /unlock messages"),
            parse_mode=ParseMode.HTML,
        )
        return

    lock_type = args[0].lower()
    if lock_type not in LOCK_TYPES and lock_type != "all":
        await send_and_delete(
            msg,
            error(f"Unknown lock type: {mono(lock_type)}\nUse /locktypes to see all."),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        if lock_type == "all":
            await chat.set_permissions(ALL_ON)
        else:
            perm_key = LOCK_TYPES[lock_type]
            await _set_one_perm(context.bot, chat.id, perm_key, True)
            await db.set_lock(chat.id, lock_type, False)

        await send_and_delete(
            msg,
            success(f"{bold(lock_type.title())} unlocked for all members."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /locktypes ────────────────────────────────────────────────────────────────

async def locktypes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    unique = sorted(set(LOCK_TYPES))
    types = "\n".join(f"  • {mono(t)}" for t in unique)
    await send_and_delete(
        update.effective_message,
        f"{header('Available Lock Types')}\n\n{types}",
        parse_mode=ParseMode.HTML,
    )


def register(app):
    app.add_handler(CommandHandler("lock", lock))
    app.add_handler(CommandHandler("unlock", unlock))
    app.add_handler(CommandHandler("locktypes", locktypes))
