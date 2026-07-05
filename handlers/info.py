"""
Info commands: id, info, chatinfo, adminlist, invite.
All bot replies auto-delete after 5 minutes.
"""
from __future__ import annotations
from telegram import Update, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

from helpers.formatting import bold, italic, mono, mention, header, info_line, error, success
from helpers.utils import send_and_delete
from config import OWNER_IDS


async def _get_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    args = context.args or []
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    if args:
        try:
            return await context.bot.get_chat(args[0].lstrip("@"))
        except Exception:
            pass
    return update.effective_user


# ── /id ───────────────────────────────────────────────────────────────────────

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    lines = [
        f"{info_line('Chat ID', str(chat.id))}",
        f"{info_line('Your ID', str(update.effective_user.id))}",
    ]
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        lines.append(f"{info_line('Replied user ID', str(u.id))}")
    await send_and_delete(msg, "\n".join(lines), parse_mode=ParseMode.HTML)


# ── /info ─────────────────────────────────────────────────────────────────────

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_target(update, context)
    chat = update.effective_chat
    msg = update.effective_message

    try:
        member = await chat.get_member(user.id)
        status = member.status
    except Exception:
        status = "unknown"

    is_owner_flag = user.id in OWNER_IDS

    lines = [
        header("User Info"),
        "",
        info_line("Name", user.full_name),
        info_line("ID", str(user.id)),
        info_line("Username", f"@{user.username}" if user.username else "None"),
        info_line("Status", status),
        info_line("Bot", "Yes" if user.is_bot else "No"),
        info_line("Bot Owner", "✅ Yes" if is_owner_flag else "No"),
    ]
    await send_and_delete(msg, "\n".join(lines), parse_mode=ParseMode.HTML)


# ── /chatinfo ─────────────────────────────────────────────────────────────────

async def chatinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    members = await context.bot.get_chat_member_count(chat.id)
    lines = [
        header("Chat Info"),
        "",
        info_line("Name", chat.title or "—"),
        info_line("ID", str(chat.id)),
        info_line("Type", chat.type),
        info_line("Username", f"@{chat.username}" if chat.username else "Private"),
        info_line("Members", str(members)),
        info_line("Description", (chat.description or "None")[:60]),
    ]
    await send_and_delete(msg, "\n".join(lines), parse_mode=ParseMode.HTML)


# ── /adminlist ────────────────────────────────────────────────────────────────

async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    admins = await chat.get_administrators()
    lines = [header("Admin List"), ""]
    for a in admins:
        u = a.user
        if u.is_bot:
            continue
        title = getattr(a, "custom_title", None) or ("Owner" if isinstance(a, ChatMemberOwner) else "Admin")
        lines.append(f"  • {mention(u.full_name, u.id)} — {italic(title)}")
    await send_and_delete(msg, "\n".join(lines), parse_mode=ParseMode.HTML)


# ── /invite ───────────────────────────────────────────────────────────────────

async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message
    try:
        link = await context.bot.export_chat_invite_link(chat.id)
        await send_and_delete(
            msg,
            f"{header('Invite Link')}\n\n{mono(link)}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


def register(app):
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("chatinfo", chatinfo))
    app.add_handler(CommandHandler("adminlist", adminlist))
    app.add_handler(CommandHandler("invite", invite))
