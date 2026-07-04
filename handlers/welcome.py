"""
Welcome / Goodbye message handlers.
"""
from __future__ import annotations
from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes, CommandHandler, ChatMemberHandler
from telegram.constants import ParseMode, ChatMemberStatus

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, italic, mono, mention, error, success, header, info_line


def _format_msg(text: str, user, chat) -> str:
    return (
        text
        .replace("{name}", mention(user.full_name, user.id))
        .replace("{username}", f"@{user.username}" if user.username else user.full_name)
        .replace("{chat}", bold(chat.title))
        .replace("{id}", mono(str(user.id)))
        .replace("{count}", mono(str(chat.id)))
    )


# ── New member handler ────────────────────────────────────────────────────────

async def on_member_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result: ChatMemberUpdated = update.chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    if old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) and \
            new_status in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
        user = result.new_chat_member.user
        chat = result.chat
        await db.register_chat(chat.id, chat.title)

        # captcha check — restrict until verified
        if await db.get_captcha(chat.id):
            db._pending_captcha[(chat.id, user.id)] = 0
            try:
                from telegram import ChatPermissions
                await context.bot.restrict_chat_member(
                    chat.id,
                    user.id,
                    ChatPermissions(can_send_messages=False),
                )
            except Exception:
                pass
            await context.bot.send_message(
                chat.id,
                f"{mention(user.full_name, user.id)}, you are restricted until you type {mono('/verify')} to prove you are human.",
                parse_mode=ParseMode.HTML,
            )
            return

        wtext = await db.get_welcome(chat.id)
        if wtext:
            msg = _format_msg(wtext, user, chat)
            await context.bot.send_message(chat.id, msg, parse_mode=ParseMode.HTML)


async def on_member_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result: ChatMemberUpdated = update.chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    if old_status == ChatMemberStatus.MEMBER and new_status == ChatMemberStatus.LEFT:
        user = result.old_chat_member.user
        chat = result.chat
        gtext = await db.get_goodbye(chat.id)
        if gtext:
            msg = _format_msg(gtext, user, chat)
            await context.bot.send_message(chat.id, msg, parse_mode=ParseMode.HTML)


# ── /welcome ──────────────────────────────────────────────────────────────────

@admin_only
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    text = await db.get_welcome(chat.id)
    if not text:
        await update.message.reply_text(
            f"{bold('No welcome message set.')}\n{italic('Use /setwelcome <text> to set one.')}",
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text(
        f"{header('Current Welcome Message')}\n\n{text}",
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    if not args:
        await update.message.reply_text(
            f"{error('Usage:')} /setwelcome <message>\n\n"
            f"{italic('Placeholders:')}\n"
            f"  {mono('{name}')} — user mention\n"
            f"  {mono('{username}')} — @username\n"
            f"  {mono('{chat}')} — group name",
            parse_mode=ParseMode.HTML,
        )
        return
    text = " ".join(args)
    await db.set_welcome(chat.id, text)
    await update.message.reply_text(
        success("Welcome message saved!"),
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def clearwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await db.clear_welcome(chat.id)
    await update.message.reply_text(
        success("Welcome message cleared."),
        parse_mode=ParseMode.HTML,
    )


# ── /goodbye ──────────────────────────────────────────────────────────────────

@admin_only
async def goodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    text = await db.get_goodbye(chat.id)
    if not text:
        await update.message.reply_text(
            f"{bold('No goodbye message set.')}\n{italic('Use /setgoodbye <text> to set one.')}",
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text(
        f"{header('Current Goodbye Message')}\n\n{text}",
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    if not args:
        await update.message.reply_text(
            error("Usage: /setgoodbye <message>"),
            parse_mode=ParseMode.HTML,
        )
        return
    text = " ".join(args)
    await db.set_goodbye(chat.id, text)
    await update.message.reply_text(
        success("Goodbye message saved!"),
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def cleargoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await db.clear_goodbye(chat.id)
    await update.message.reply_text(
        success("Goodbye message cleared."),
        parse_mode=ParseMode.HTML,
    )


# ── /verify (captcha) ─────────────────────────────────────────────────────────

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    key = (chat.id, user.id)
    if key in db._pending_captcha:
        del db._pending_captcha[key]
        # restore permissions
        try:
            from telegram import ChatPermissions
            await chat.restrict_member(
                user.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                ),
            )
        except Exception:
            pass
        await update.message.reply_text(
            success(f"Welcome, {mention(user.full_name, user.id)}! You are verified ✅"),
            parse_mode=ParseMode.HTML,
        )
        wtext = await db.get_welcome(chat.id)
        if wtext:
            await context.bot.send_message(
                chat.id, _format_msg(wtext, user, chat), parse_mode=ParseMode.HTML
            )


def register(app):
    app.add_handler(ChatMemberHandler(on_member_join, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_member_leave, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler("welcome", welcome))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("clearwelcome", clearwelcome))
    app.add_handler(CommandHandler("goodbye", goodbye))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye))
    app.add_handler(CommandHandler("cleargoodbye", cleargoodbye))
    app.add_handler(CommandHandler("verify", verify))
