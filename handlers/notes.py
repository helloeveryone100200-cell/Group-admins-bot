"""
Notes commands — save, get, list, delete notes per group.
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, italic, mono, error, success, header


# ── /note <name> <text> ───────────────────────────────────────────────────────

@admin_only
async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if len(args) < 2:
        await msg.reply_text(
            f"{error('Usage:')} /note {italic('<name>')} {italic('<text>')}",
            parse_mode=ParseMode.HTML,
        )
        return
    name = args[0].lower()
    text = " ".join(args[1:])
    await db.save_note(chat.id, name, text)
    await msg.reply_text(
        success(f"Note {mono(name)} saved!"),
        parse_mode=ParseMode.HTML,
    )


# ── /get <name> or #notename ──────────────────────────────────────────────────

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    if not args:
        await update.message.reply_text(
            error("Usage: /get <name>"),
            parse_mode=ParseMode.HTML,
        )
        return
    name = args[0].lower()
    text = await db.get_note(chat.id, name)
    if not text:
        await update.message.reply_text(
            error(f"No note named {mono(name)} found."),
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text(
        f"{header(f'Note: {name}')}\n\n{text}",
        parse_mode=ParseMode.HTML,
    )


# ── Hashtag shortcut: #notename ───────────────────────────────────────────────

async def hash_get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg.text:
        return
    for word in msg.text.split():
        if word.startswith("#") and len(word) > 1:
            name = word[1:].lower()
            text = await db.get_note(chat.id, name)
            if text:
                await msg.reply_text(
                    f"{header(f'Note: {name}')}\n\n{text}",
                    parse_mode=ParseMode.HTML,
                )


# ── /notes ────────────────────────────────────────────────────────────────────

async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    note_list = await db.get_all_notes(chat.id)
    if not note_list:
        await update.message.reply_text(
            f"{bold('No notes saved in this group.')}",
            parse_mode=ParseMode.HTML,
        )
        return
    lines = "\n".join(f"  • {mono(n)}" for n in sorted(note_list))
    await update.message.reply_text(
        f"{header('Saved Notes')}\n\n{lines}\n\n{italic('Use #notename or /get <name> to retrieve.')}",
        parse_mode=ParseMode.HTML,
    )


# ── /clearnote <name> ─────────────────────────────────────────────────────────

@admin_only
async def clear_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    if not args:
        await update.message.reply_text(
            error("Usage: /clearnote <name>"),
            parse_mode=ParseMode.HTML,
        )
        return
    name = args[0].lower()
    deleted = await db.delete_note(chat.id, name)
    if deleted:
        await update.message.reply_text(
            success(f"Note {mono(name)} deleted."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            error(f"No note named {mono(name)} found."),
            parse_mode=ParseMode.HTML,
        )


# ── /clearallnotes ────────────────────────────────────────────────────────────

@admin_only
async def clear_all_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await db.delete_all_notes(chat.id)
    await update.message.reply_text(
        success("All notes cleared for this group."),
        parse_mode=ParseMode.HTML,
    )


def register(app):
    app.add_handler(CommandHandler("note", save_note))
    app.add_handler(CommandHandler("get", get_note))
    app.add_handler(CommandHandler("notes", list_notes))
    app.add_handler(CommandHandler("clearnote", clear_note))
    app.add_handler(CommandHandler("clearallnotes", clear_all_notes))
    app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"#\w+") & ~filters.COMMAND, hash_get)
    )
