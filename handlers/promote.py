"""
Promote, demote, admin title commands.
All bot replies auto-delete after 5 minutes.
"""
from __future__ import annotations
from telegram import Update, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import bold, italic, mono, mention, error, success, header, info_line
from helpers.utils import send_and_delete


async def _get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = context.args or []
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user, " ".join(args)
    if args:
        try:
            user = await context.bot.get_chat(args[0].lstrip("@"))
            return user, " ".join(args[1:])
        except Exception:
            pass
    return None, ""


# ── /promote ──────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, title = await _get_target(update, context)
    chat = update.effective_chat
    msg = update.effective_message
    if not user:
        await send_and_delete(
            msg,
            error("Reply to a user or provide @username to promote."),
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        await chat.promote_member(
            user.id,
            can_change_info=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_manage_chat=True,
            can_manage_video_chats=True,
        )
        if title:
            try:
                await context.bot.set_chat_administrator_custom_title(chat.id, user.id, title[:16])
            except Exception:
                pass
        await send_and_delete(
            msg,
            f"{header('Admin Promoted')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('Title', title or 'Admin')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /demote ───────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _get_target(update, context)
    chat = update.effective_chat
    msg = update.effective_message
    if not user:
        await send_and_delete(
            msg,
            error("Reply to a user or provide @username to demote."),
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        await chat.promote_member(
            user.id,
            can_change_info=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False,
            can_pin_messages=False,
            can_manage_chat=False,
            can_manage_video_chats=False,
        )
        await send_and_delete(
            msg,
            success(f"{mention(user.full_name, user.id)} has been {bold('demoted')}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /title ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, ttl = await _get_target(update, context)
    chat = update.effective_chat
    msg = update.effective_message
    if not user or not ttl:
        await send_and_delete(
            msg,
            f"{error('Usage:')} /title @username {italic('custom title')}",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        await context.bot.set_chat_administrator_custom_title(chat.id, user.id, ttl[:16])
        await send_and_delete(
            msg,
            success(f"Admin title for {mention(user.full_name, user.id)} set to {mono(ttl[:16])}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("demote", demote))
    app.add_handler(CommandHandler("title", title))
