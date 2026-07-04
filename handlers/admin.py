"""
Admin commands: ban, unban, tban, mute, unmute, tmute, kick, warn, unwarn, resetwarn, warnings, warnlimit
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone

from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, CommandHandler
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only, bot_admin_required
from helpers.formatting import bold, italic, mono, mention, error, success, warn_msg, header, info_line


def _parse_time(arg: str) -> timedelta | None:
    """Parse '10m', '2h', '1d' into a timedelta. Returns None if invalid."""
    match = re.match(r"^(\d+)([mhd])$", arg.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return timedelta(minutes=value if unit == "m" else 0,
                     hours=value if unit == "h" else 0,
                     days=value if unit == "d" else 0)


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return (user, reason_args) from reply or mention."""
    msg = update.effective_message
    args = context.args or []

    if msg.reply_to_message and msg.reply_to_message.from_user:
        user = msg.reply_to_message.from_user
        reason = " ".join(args)
        return user, reason

    if args:
        try:
            user = await context.bot.get_chat(args[0].lstrip("@"))
            reason = " ".join(args[1:])
            return user, reason
        except Exception:
            pass

    return None, ""


# ── /ban ─────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, reason = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to ban."), parse_mode=ParseMode.HTML)
        return
    try:
        await chat.ban_member(user.id)
        text = (
            f"{header('User Banned')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('ID', str(user.id))}\n"
            f"{info_line('Reason', reason or 'No reason given')}\n"
            f"{italic('Banned by')} {mention(update.effective_user.full_name, update.effective_user.id)}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /unban ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to unban."), parse_mode=ParseMode.HTML)
        return
    try:
        await chat.unban_member(user.id)
        await update.message.reply_text(
            success(f"{mention(user.full_name, user.id)} has been {bold('unbanned')}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /tban ─────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def tban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(
            error("Usage: /tban [username] <time>\nTime: <code>10m</code> / <code>2h</code> / <code>1d</code>"),
            parse_mode=ParseMode.HTML,
        )
        return
    # last arg is time
    duration = _parse_time(args[-1])
    if not duration:
        await update.message.reply_text(error("Invalid time format. Use 10m / 2h / 1d."), parse_mode=ParseMode.HTML)
        return
    context.args = args[:-1] or []
    user, reason = await _resolve_target(update, context)
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username."), parse_mode=ParseMode.HTML)
        return
    until = datetime.now(timezone.utc) + duration
    try:
        await update.effective_chat.ban_member(user.id, until_date=until)
        await update.message.reply_text(
            f"{header('Temp Ban')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('Duration', args[-1])}\n"
            f"{info_line('Reason', reason or 'No reason given')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /kick ─────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, reason = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to kick."), parse_mode=ParseMode.HTML)
        return
    try:
        await chat.ban_member(user.id)
        await chat.unban_member(user.id)
        await update.message.reply_text(
            f"{header('User Kicked')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('Reason', reason or 'No reason given')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /mute ─────────────────────────────────────────────────────────────────────

MUTE_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

UNMUTE_PERMS = ChatPermissions(
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
)


@admin_only
@bot_admin_required
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, reason = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to mute."), parse_mode=ParseMode.HTML)
        return
    try:
        await chat.restrict_member(user.id, MUTE_PERMS)
        await update.message.reply_text(
            f"{header('User Muted')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('Reason', reason or 'No reason given')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /unmute ───────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to unmute."), parse_mode=ParseMode.HTML)
        return
    try:
        await chat.restrict_member(user.id, UNMUTE_PERMS)
        await update.message.reply_text(
            success(f"{mention(user.full_name, user.id)} has been {bold('unmuted')}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /tmute ────────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def tmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.message.reply_text(
            error("Usage: /tmute [username] <time>\nTime: <code>10m</code> / <code>2h</code> / <code>1d</code>"),
            parse_mode=ParseMode.HTML,
        )
        return
    duration = _parse_time(args[-1])
    if not duration:
        await update.message.reply_text(error("Invalid time format. Use 10m / 2h / 1d."), parse_mode=ParseMode.HTML)
        return
    context.args = args[:-1] or []
    user, reason = await _resolve_target(update, context)
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username."), parse_mode=ParseMode.HTML)
        return
    until = datetime.now(timezone.utc) + duration
    try:
        await update.effective_chat.restrict_member(user.id, MUTE_PERMS, until_date=until)
        await update.message.reply_text(
            f"{header('Temp Mute')}\n\n"
            f"{info_line('User', mention(user.full_name, user.id))}\n"
            f"{info_line('Duration', args[-1])}\n"
            f"{info_line('Reason', reason or 'No reason given')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await update.message.reply_text(error(str(e)), parse_mode=ParseMode.HTML)


# ── /warn ─────────────────────────────────────────────────────────────────────

@admin_only
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, reason = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user or provide @username to warn."), parse_mode=ParseMode.HTML)
        return
    count = await db.add_warn(chat.id, user.id, reason or "No reason given")
    limit = await db.get_warn_limit(chat.id)
    text = (
        f"{warn_msg('Warning Issued')}\n\n"
        f"{info_line('User', mention(user.full_name, user.id))}\n"
        f"{info_line('Warns', f'{count}/{limit}')}\n"
        f"{info_line('Reason', reason or 'No reason given')}"
    )
    if count >= limit:
        try:
            await chat.ban_member(user.id)
            text += f"\n\n{bold('⛔ Auto-banned — warn limit reached!')}"
        except Exception:
            pass
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ── /unwarn ───────────────────────────────────────────────────────────────────

@admin_only
async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user to remove their last warning."), parse_mode=ParseMode.HTML)
        return
    remaining = await db.remove_warn(chat.id, user.id)
    limit = await db.get_warn_limit(chat.id)
    await update.message.reply_text(
        success(f"Last warning removed for {mention(user.full_name, user.id)}.\n"
                f"{info_line('Warns', f'{remaining}/{limit}')}"),
        parse_mode=ParseMode.HTML,
    )


# ── /resetwarn ────────────────────────────────────────────────────────────────

@admin_only
async def resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _resolve_target(update, context)
    chat = update.effective_chat
    if not user:
        await update.message.reply_text(error("Reply to a user to reset their warnings."), parse_mode=ParseMode.HTML)
        return
    await db.reset_warns(chat.id, user.id)
    await update.message.reply_text(
        success(f"All warnings reset for {mention(user.full_name, user.id)}."),
        parse_mode=ParseMode.HTML,
    )


# ── /warnings ─────────────────────────────────────────────────────────────────

async def warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user, _ = await _resolve_target(update, context)
    if not user:
        user = update.effective_user
    chat = update.effective_chat
    warns_list = await db.get_warns(chat.id, user.id)
    limit = await db.get_warn_limit(chat.id)
    if not warns_list:
        await update.message.reply_text(
            f"{mention(user.full_name, user.id)} has {bold('no warnings')}.",
            parse_mode=ParseMode.HTML,
        )
        return
    lines = "\n".join(f"  {i+1}. {mono(w)}" for i, w in enumerate(warns_list))
    await update.message.reply_text(
        f"{header('Warnings')}\n\n"
        f"{info_line('User', mention(user.full_name, user.id))}\n"
        f"{info_line('Count', f'{len(warns_list)}/{limit}')}\n\n"
        f"{bold('Reasons:')}\n{lines}",
        parse_mode=ParseMode.HTML,
    )


# ── /warnlimit ────────────────────────────────────────────────────────────────

@admin_only
async def warnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    chat = update.effective_chat
    if not args or not args[0].isdigit():
        limit = await db.get_warn_limit(chat.id)
        await update.message.reply_text(
            f"{info_line('Current warn limit', str(limit))}\n"
            f"{italic('Use /warnlimit <number> to change.')}",
            parse_mode=ParseMode.HTML,
        )
        return
    new_limit = int(args[0])
    if new_limit < 1:
        await update.message.reply_text(error("Warn limit must be at least 1."), parse_mode=ParseMode.HTML)
        return
    await db.set_warn_limit(chat.id, new_limit)
    await update.message.reply_text(
        success(f"Warn limit set to {bold(str(new_limit))}."),
        parse_mode=ParseMode.HTML,
    )


# ── Register handlers ─────────────────────────────────────────────────────────

def register(app):
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("tban", tban))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("tmute", tmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("resetwarn", resetwarn))
    app.add_handler(CommandHandler("warnings", warnings))
    app.add_handler(CommandHandler("warnlimit", warnlimit))
