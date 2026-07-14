"""
Fun plugin — zero core-code changes required to add/remove.

Drop this file in plugins/ to activate; delete it to remove.

Commands:
  /dice     — Roll a D6 dice (1-6)
  /coinflip — Flip a coin (Heads / Tails)
  /8ball    — Ask the magic 8-ball
"""
from __future__ import annotations
import random

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

import database as db
from helpers.i18n import t

_8BALL_ANSWERS_EN = [
    "It is certain.", "Without a doubt.", "Yes, definitely!",
    "Most likely.", "Outlook good.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.",
    "Don't count on it.", "My sources say no.",
    "Very doubtful.", "Outlook not so good.", "My reply is no.",
]


async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = await db.get_lang(chat.id) if chat else "en"
    result = random.randint(1, 6)
    faces  = ["", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    await update.effective_message.reply_text(
        t(lang, "dice_result", result=f"{faces[result]}  ({result})"),
        parse_mode=ParseMode.HTML,
    )


async def coinflip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = await db.get_lang(chat.id) if chat else "en"
    key  = "coin_heads" if random.random() < 0.5 else "coin_tails"
    await update.effective_message.reply_text(t(lang, key), parse_mode=ParseMode.HTML)


async def eightball(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat     = update.effective_chat
    lang     = await db.get_lang(chat.id) if chat else "en"
    question = " ".join(context.args) if context.args else "..."
    answer   = random.choice(_8BALL_ANSWERS_EN)
    await update.effective_message.reply_text(
        t(lang, "8ball_q", question=question, answer=answer),
        parse_mode=ParseMode.HTML,
    )


def register(app) -> None:
    """Called automatically by bot.py's plugin loader."""
    app.add_handler(CommandHandler("dice",     dice))
    app.add_handler(CommandHandler("coinflip", coinflip))
    app.add_handler(CommandHandler("8ball",    eightball))
