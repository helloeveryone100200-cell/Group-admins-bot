"""
Purge / del commands.
All bot replies auto-delete after 5 minutes.
Note: purgefrom removed — PTB v21 does not expose iter_history_updates.
"""
from __future__ import annotations
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import error, success, bold
from helpers.utils import send_and_delete, _delete_later, AUTO_DELETE_DELAY


# ── /del ──────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await send_and_delete(
            msg, error("Reply to a message to delete it."), parse_mode=ParseMode.HTML
        )
        return
    try:
        await msg.reply_to_message.delete()
        await msg.delete()
    except BadRequest as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /purge ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message:
        await send_and_delete(
            msg,
            error("Reply to the first message you want to purge."),
            parse_mode=ParseMode.HTML,
        )
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
    await asyncio.sleep(3)
    try:
        await note.delete()
    except Exception:
        pass


def register(app):
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(CommandHandler("purge", purge))
