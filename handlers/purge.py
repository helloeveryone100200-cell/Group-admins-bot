"""
Purge / purgefrom / del commands.
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import error, success, bold, mono


# ── /del ──────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text(error("Reply to a message to delete it."), parse_mode=ParseMode.HTML)
        return
    try:
        await msg.reply_to_message.delete()
        await msg.delete()
    except BadRequest as e:
        await msg.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /purge ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await msg.reply_text(error("Reply to the first message you want to purge."), parse_mode=ParseMode.HTML)
        return
    start_id = msg.reply_to_message.message_id
    end_id = msg.message_id
    chat_id = update.effective_chat.id

    deleted = 0
    ids_to_delete = list(range(start_id, end_id + 1))

    # Telegram allows up to 100 messages at once via deleteMessages
    for i in range(0, len(ids_to_delete), 100):
        batch = ids_to_delete[i:i + 100]
        try:
            await context.bot.delete_messages(chat_id, batch)
            deleted += len(batch)
        except BadRequest:
            for mid in batch:
                try:
                    await context.bot.delete_message(chat_id, mid)
                    deleted += 1
                except BadRequest:
                    pass

    note = await update.effective_chat.send_message(
        success(f"{bold(str(deleted))} messages purged."),
        parse_mode=ParseMode.HTML,
    )
    import asyncio
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


# ── /purgefrom ────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def purgefrom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Purge all messages from a specific user in the last N messages."""
    msg = update.effective_message
    args = context.args or []
    chat = update.effective_chat

    if not msg.reply_to_message:
        await msg.reply_text(
            error("Reply to a message from the user whose messages you want to purge."),
            parse_mode=ParseMode.HTML,
        )
        return

    target_user_id = msg.reply_to_message.from_user.id if msg.reply_to_message.from_user else None
    if not target_user_id:
        await msg.reply_text(error("Cannot determine the target user."), parse_mode=ParseMode.HTML)
        return

    limit = 200
    if args and args[0].isdigit():
        limit = min(int(args[0]), 1000)

    deleted = 0
    async for m in chat.iter_history_updates(limit=limit):
        if m.from_user and m.from_user.id == target_user_id:
            try:
                await context.bot.delete_message(chat.id, m.message_id)
                deleted += 1
            except BadRequest:
                pass

    await msg.reply_text(
        success(f"Deleted {bold(str(deleted))} messages from that user."),
        parse_mode=ParseMode.HTML,
    )


def register(app):
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(CommandHandler("purge", purge))
    app.add_handler(CommandHandler("purgefrom", purgefrom))
