"""
Filters (keyword auto-reply) and Blacklist commands.
All bot command replies auto-delete after 5 minutes.
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, italic, mono, mention, error, success, header
from helpers.utils import send_and_delete


# ═══════════════════════════════════════════════════════
#  FILTERS
# ═══════════════════════════════════════════════════════

@admin_only
async def add_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if len(args) < 2:
        await send_and_delete(
            msg,
            f"{error('Usage:')} /filter {italic('&lt;keyword&gt;')} {italic('&lt;reply text&gt;')}",
            parse_mode=ParseMode.HTML,
        )
        return
    keyword = args[0].lower()
    reply = " ".join(args[1:])
    await db.add_filter(chat.id, keyword, reply)
    await send_and_delete(
        msg,
        success(f"Filter {mono(keyword)} added!"),
        parse_mode=ParseMode.HTML,
    )


async def list_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    kws = await db.get_all_filters(chat.id)
    if not kws:
        await send_and_delete(
            msg,
            bold("No filters set in this group."),
            parse_mode=ParseMode.HTML,
        )
        return
    lines = "\n".join(f"  • {mono(k)}" for k in sorted(kws))
    await send_and_delete(
        msg,
        f"{header('Active Filters')}\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def stop_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if not args:
        await send_and_delete(
            msg, error("Usage: /stop &lt;keyword&gt;"), parse_mode=ParseMode.HTML
        )
        return
    keyword = args[0].lower()
    deleted = await db.delete_filter(chat.id, keyword)
    if deleted:
        await send_and_delete(
            msg,
            success(f"Filter {mono(keyword)} removed."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await send_and_delete(
            msg,
            error(f"No filter {mono(keyword)} found."),
            parse_mode=ParseMode.HTML,
        )


@admin_only
async def stop_all_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await db.delete_all_filters(chat.id)
    await send_and_delete(
        update.effective_message,
        success("All filters cleared."),
        parse_mode=ParseMode.HTML,
    )


async def reply_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-reply to filtered keywords."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not msg.text:
        return
    text_lower = msg.text.lower()
    filters_list = await db.get_all_filters(chat.id)
    for kw in filters_list:
        if kw in text_lower:
            reply = await db.get_filter(chat.id, kw)
            if reply:
                await msg.reply_text(reply, parse_mode=ParseMode.HTML)
            break


# ═══════════════════════════════════════════════════════
#  BLACKLIST
# ═══════════════════════════════════════════════════════

@admin_only
async def blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if not args:
        words = await db.get_blacklist(chat.id)
        if not words:
            await send_and_delete(
                msg,
                bold("No blacklisted words in this group."),
                parse_mode=ParseMode.HTML,
            )
            return
        lines = "\n".join(f"  • {mono(w)}" for w in sorted(words))
        await send_and_delete(
            msg,
            f"{header('Blacklisted Words')}\n\n{lines}",
            parse_mode=ParseMode.HTML,
        )
        return
    word = " ".join(args).lower()
    await db.add_blacklist(chat.id, word)
    await send_and_delete(
        msg,
        success(f"Word {mono(word)} added to blacklist."),
        parse_mode=ParseMode.HTML,
    )


@admin_only
async def unblacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    if not args:
        await send_and_delete(
            msg, error("Usage: /unblacklist &lt;word&gt;"), parse_mode=ParseMode.HTML
        )
        return
    word = " ".join(args).lower()
    removed = await db.remove_blacklist(chat.id, word)
    if removed:
        await send_and_delete(
            msg,
            success(f"Word {mono(word)} removed from blacklist."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await send_and_delete(
            msg,
            error(f"Word {mono(word)} not in blacklist."),
            parse_mode=ParseMode.HTML,
        )


@admin_only
async def blmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = context.args or []
    msg = update.effective_message
    modes = ["delete", "warn", "mute", "kick", "ban"]
    if not args or args[0].lower() not in modes:
        current = await db.get_blacklist_mode(chat.id)
        opts = " | ".join(mono(m) for m in modes)
        await send_and_delete(
            msg,
            f"{header('Blacklist Mode')}\n\n"
            f"{bold('Current:')} {mono(current)}\n\n"
            f"{italic('Options:')} {opts}\n"
            f"{italic('Usage:')} /blmode &lt;mode&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    mode = args[0].lower()
    await db.set_blacklist_mode(chat.id, mode)
    await send_and_delete(
        msg,
        success(f"Blacklist action set to {bold(mode)}."),
        parse_mode=ParseMode.HTML,
    )


async def check_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-enforce blacklisted words."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not msg.text or not user:
        return
    # admins are exempt
    from telegram import ChatMemberAdministrator, ChatMemberOwner
    member = await chat.get_member(user.id)
    if isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
        return

    text_lower = msg.text.lower()
    words = await db.get_blacklist(chat.id)
    triggered = any(w in text_lower for w in words)
    if not triggered:
        return

    mode = await db.get_blacklist_mode(chat.id)
    try:
        await msg.delete()
    except Exception:
        pass

    from handlers.admin import MUTE_PERMS
    if mode == "warn":
        count = await db.add_warn(chat.id, user.id, "Blacklisted word")
        limit = await db.get_warn_limit(chat.id)
        await chat.send_message(
            f"{mention(user.full_name, user.id)} warned for using a blacklisted word. "
            f"{bold(f'{count}/{limit}')} warnings.",
            parse_mode=ParseMode.HTML,
        )
    elif mode == "mute":
        await chat.restrict_member(user.id, MUTE_PERMS)
        await chat.send_message(
            f"{mention(user.full_name, user.id)} has been {bold('muted')} for using a blacklisted word.",
            parse_mode=ParseMode.HTML,
        )
    elif mode == "kick":
        await chat.ban_member(user.id)
        await chat.unban_member(user.id)
        await chat.send_message(
            f"{mention(user.full_name, user.id)} has been {bold('kicked')} for using a blacklisted word.",
            parse_mode=ParseMode.HTML,
        )
    elif mode == "ban":
        await chat.ban_member(user.id)
        await chat.send_message(
            f"{mention(user.full_name, user.id)} has been {bold('banned')} for using a blacklisted word.",
            parse_mode=ParseMode.HTML,
        )


def register(app):
    app.add_handler(CommandHandler("filter", add_filter))
    app.add_handler(CommandHandler("filters", list_filters))
    app.add_handler(CommandHandler("stop", stop_filter))
    app.add_handler(CommandHandler("stopall", stop_all_filters))
    app.add_handler(CommandHandler("blacklist", blacklist))
    app.add_handler(CommandHandler("unblacklist", unblacklist))
    app.add_handler(CommandHandler("blmode", blmode))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, check_blacklist), group=10
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, reply_filter), group=11
    )
