"""
Permission decorators for all command handlers.
"""
from __future__ import annotations
import functools
from telegram import Update, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import OWNER_IDS
from helpers.formatting import error


def _is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


async def _is_admin(update: Update) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False
    member = await update.effective_chat.get_member(update.effective_user.id)
    return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))


async def _bot_is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat:
        return False
    me = await context.bot.get_chat_member(
        update.effective_chat.id, context.bot.id
    )
    return isinstance(me, (ChatMemberAdministrator, ChatMemberOwner))


def owner_only(func):
    """Only OWNER_IDS may run this command."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not _is_owner(update.effective_user.id):
            await update.effective_message.reply_text(
                error("This command is restricted to the bot owner."),
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper


def admin_only(func):
    """Group admins and bot owners may run this command."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        if _is_owner(update.effective_user.id):
            return await func(update, context)
        if update.effective_chat and update.effective_chat.type == "private":
            await update.effective_message.reply_text(
                error("Use this command in a group."),
                parse_mode=ParseMode.HTML,
            )
            return
        if not await _is_admin(update):
            await update.effective_message.reply_text(
                error("You must be an admin to use this command."),
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper


def bot_admin_required(func):
    """Also checks that the bot itself has admin rights."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await _bot_is_admin(update, context):
            await update.effective_message.reply_text(
                error("I need admin rights to perform this action."),
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper
