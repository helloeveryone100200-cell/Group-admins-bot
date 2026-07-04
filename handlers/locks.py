"""
Lock / unlock chat permissions.
"""
from __future__ import annotations
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import error, success, bold, mono, header, italic

LOCK_TYPES = {
    "messages":  "can_send_messages",
    "media":     "can_send_other_messages",
    "stickers":  "can_send_other_messages",
    "gifs":      "can_send_other_messages",
    "polls":     "can_send_polls",
    "forwards":  "can_forward_messages",
    "invite":    "can_invite_users",
    "pin":       "can_pin_messages",
    "info":      "can_change_info",
    "webprev":   "can_add_web_page_previews",
}

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


# ── /lock ─────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    chat = update.effective_chat
    if not args:
        types = "\n".join(f"  • {mono(t)}" for t in LOCK_TYPES)
        await update.message.reply_text(
            f"{header('Lock Types')}\n\n{types}\n\n{italic('Example:')} {mono('/lock messages')}",
            parse_mode=ParseMode.HTML,
        )
        return
    lock_type = args[0].lower()
    if lock_type not in LOCK_TYPES and lock_type != "all":
        await update.message.reply_text(error(f"Unknown lock type: {mono(lock_type)}"), parse_mode=ParseMode.HTML)
        return
    try:
        if lock_type == "all":
            await chat.set_permissions(ALL_OFF)
        else:
            await db.set_lock(chat.id, lock_type, True)
        await update.message.reply_text(
            success(f"{bold(lock_type.title())} locked for all members."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /unlock ───────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    chat = update.effective_chat
    if not args:
        await update.message.reply_text(
            error("Usage: /unlock <type> — e.g. /unlock messages"),
            parse_mode=ParseMode.HTML,
        )
        return
    lock_type = args[0].lower()
    if lock_type not in LOCK_TYPES and lock_type != "all":
        await update.message.reply_text(error(f"Unknown lock type: {mono(lock_type)}"), parse_mode=ParseMode.HTML)
        return
    try:
        if lock_type == "all":
            await chat.set_permissions(ALL_ON)
        else:
            await db.set_lock(chat.id, lock_type, False)
        await update.message.reply_text(
            success(f"{bold(lock_type.title())} unlocked for all members."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /locktypes ────────────────────────────────────────────────────────────────

async def locktypes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types = "\n".join(f"  • {mono(t)}" for t in LOCK_TYPES)
    await update.message.reply_text(
        f"{header('Available Lock Types')}\n\n{types}",
        parse_mode=ParseMode.HTML,
    )


def register(app):
    app.add_handler(CommandHandler("lock", lock))
    app.add_handler(CommandHandler("unlock", unlock))
    app.add_handler(CommandHandler("locktypes", locktypes))
