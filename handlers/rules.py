"""
Group rules commands.
All bot replies auto-delete after 5 minutes.
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, italic, error, success, header
from helpers.utils import send_and_delete


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    text = await db.get_rules(chat.id)
    if not text:
        await send_and_delete(
            msg,
            f"{bold('No rules set for this group.')}\n{italic('Admins can set rules with /setrules.')}",
            parse_mode=ParseMode.HTML,
        )
        return
    await send_and_delete(
        msg,
        f"{header('Group Rules')}\n\n{text}",
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if not args:
        await send_and_delete(
            msg,
            error("Usage: /setrules &lt;rules text&gt;"),
            parse_mode=ParseMode.HTML,
        )
        return
    text = " ".join(args)
    await db.set_rules(chat.id, text)
    await send_and_delete(msg, success("Group rules have been updated!"), parse_mode=ParseMode.HTML)


@admin_only
async def clearrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await db.clear_rules(chat.id)
    await send_and_delete(
        update.effective_message,
        success("Group rules cleared."),
        parse_mode=ParseMode.HTML,
    )


def register(app):
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("setrules", setrules))
    app.add_handler(CommandHandler("clearrules", clearrules))
