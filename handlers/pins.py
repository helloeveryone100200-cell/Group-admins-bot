"""
Pin / unpin / unpinall commands.
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import error, success, bold


# ── /pin ──────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text(error("Reply to a message to pin it."), parse_mode=ParseMode.HTML)
        return
    silent = "silent" in (context.args or [])
    try:
        await msg.reply_to_message.pin(disable_notification=silent)
        await msg.reply_text(
            success(f"Message {bold('pinned')}" + (" silently." if silent else ".")),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /unpin ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    try:
        if msg.reply_to_message:
            await context.bot.unpin_chat_message(chat.id, msg.reply_to_message.message_id)
        else:
            await context.bot.unpin_chat_message(chat.id)
        await msg.reply_text(success(f"Message {bold('unpinned')}."), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /unpinall ─────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unpinall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    try:
        await context.bot.unpin_all_chat_messages(chat.id)
        await update.message.reply_text(
            success(f"All pinned messages {bold('cleared')}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("pin", pin))
    app.add_handler(CommandHandler("unpin", unpin))
    app.add_handler(CommandHandler("unpinall", unpinall))
