"""
Miscellaneous commands:
start (inline category menu), help, ping, stats, report,
broadcast, slowmode, setdesc, settitle, captcha, antispam,
stickerban, nightmode.

/start welcome message and inline button menus are NEVER auto-deleted.
All other bot replies auto-delete after 5 minutes.
"""
from __future__ import annotations
import time
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode

import database as db
from config import OWNER_IDS, BOT_NAME, VERSION
from helpers.decorators import admin_only, owner_only, bot_admin_required
from helpers.formatting import (
    bold, italic, mono, mention, error, success, header, info_line, warn_msg,
)
from helpers.utils import send_and_delete, AUTO_DELETE_DELAY, _delete_later


# ── Category help texts ───────────────────────────────────────────────────────

_CAT = {
    "moderation": (
        "🛡️ <b>Moderation</b>\n\n"
        "/ban — Ban a user\n"
        "/unban — Unban a user\n"
        "/tban — Temp ban (e.g. /tban @user 1h)\n"
        "/kick — Kick a user\n"
        "/mute — Mute a user\n"
        "/unmute — Unmute a user\n"
        "/tmute — Temp mute (e.g. /tmute @user 30m)\n"
        "/promote — Promote to admin\n"
        "/demote — Remove admin rights\n"
        "/title — Set custom admin title\n"
        "/pin [silent] — Pin a message\n"
        "/unpin — Unpin message\n"
        "/unpinall — Unpin all messages\n"
        "/purge — Purge messages (reply to start)\n"
        "/del — Delete a single message"
    ),
    "warnings": (
        "⚠️ <b>Warnings</b>\n\n"
        "/warn — Warn a user\n"
        "/unwarn — Remove last warning\n"
        "/resetwarn — Reset all warnings\n"
        "/warnings — Show warning count\n"
        "/warnlimit — Set warn limit (default 3)\n\n"
        "<i>When limit is reached the user is automatically banned.</i>"
    ),
    "group_control": (
        "🔒 <b>Group Control</b>\n\n"
        "/lock &lt;type&gt; — Lock a chat permission\n"
        "/unlock &lt;type&gt; — Unlock a chat permission\n"
        "/locktypes — Show all lockable types\n"
        "/slowmode &lt;seconds&gt; — Set slow mode\n"
        "/nightmode — Toggle night lock\n"
        "/setdesc &lt;text&gt; — Set group description\n"
        "/settitle &lt;text&gt; — Set group title\n"
        "/antiflood [n] — Set flood limit\n"
        "/floodmode &lt;mode&gt; — Set flood action\n"
        "/blacklist [word] — View/add blacklist\n"
        "/unblacklist &lt;word&gt; — Remove from blacklist\n"
        "/blmode &lt;mode&gt; — Set blacklist action"
    ),
    "settings": (
        "⚙️ <b>Settings</b>\n\n"
        "/welcome — Show current welcome message\n"
        "/setwelcome — Set welcome message\n"
        "/clearwelcome — Clear welcome message\n"
        "/goodbye — Show goodbye message\n"
        "/setgoodbye — Set goodbye message\n"
        "/cleargoodbye — Clear goodbye message\n"
        "/rules — Show group rules\n"
        "/setrules — Set group rules\n"
        "/clearrules — Clear group rules\n"
        "/captcha — Toggle captcha for new members\n"
        "/antispam — Toggle anti-spam\n"
        "/stickerban — Toggle sticker ban\n"
        "/filter &lt;kw&gt; &lt;reply&gt; — Add auto-reply filter\n"
        "/filters — List filters\n"
        "/stop &lt;kw&gt; — Remove a filter\n"
        "/stopall — Remove all filters\n"
        "/note &lt;name&gt; &lt;text&gt; — Save a note\n"
        "/get &lt;name&gt; — Get a note\n"
        "/notes — List all notes\n"
        "/clearnote &lt;name&gt; — Delete a note\n"
        "/clearallnotes — Delete all notes"
    ),
    "scheduling": (
        "📅 <b>Scheduling</b>\n\n"
        "<b>Add a schedule:</b>\n"
        "<code>/addschedule &lt;name&gt; one_time YYYY-MM-DD HH:MM &lt;msg&gt;</code>\n"
        "<code>/addschedule &lt;name&gt; always HH:MM &lt;msg&gt;</code>\n\n"
        "• <b>one_time</b> — fires once at the given date &amp; time, then removed\n"
        "• <b>always</b> — fires every day at the given time\n\n"
        "/schedules — List all active schedules\n"
        "/delschedule &lt;id or name&gt; — Delete a schedule"
    ),
    "id_info": (
        "🆔 <b>ID &amp; Info</b>\n\n"
        "/id — Show your / replied user's ID\n"
        "/info — Detailed user info\n"
        "/chatinfo — Chat information\n"
        "/adminlist — List all admins\n"
        "/invite — Generate invite link\n"
        "/ping — Check bot latency\n"
        "/stats — Bot statistics\n"
        "/report — Report a user to admins"
    ),
}

# ── Inline keyboard builders ──────────────────────────────────────────────────

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🛡️ MODERATION",   callback_data="help_moderation"),
            InlineKeyboardButton("⚠️ WARNINGS",     callback_data="help_warnings"),
        ],
        [
            InlineKeyboardButton("🔒 GROUP CONTROL", callback_data="help_group_control"),
            InlineKeyboardButton("⚙️ SETTINGS",      callback_data="help_settings"),
        ],
        [
            InlineKeyboardButton("📅 SCHEDULING",    callback_data="help_scheduling"),
            InlineKeyboardButton("🆔 ID & INFO",     callback_data="help_id_info"),
        ],
    ])


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("« Back", callback_data="help_main"),
    ]])


# ── /start ────────────────────────────────────────────────────────────────────
# NOTE: /start welcome message is NEVER auto-deleted.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"👋 <b>Hello, {user.full_name}!</b>\n\n"
        f"I am your <b>Group Management Bot</b>.\n"
        f"Choose a category below to see available commands."
    )
    await update.message.reply_text(
        text,
        reply_markup=_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    # Do NOT auto-delete the /start welcome message or its inline buttons.


# ── /help ─────────────────────────────────────────────────────────────────────
# NOTE: /help menu message is also NOT auto-deleted (inline buttons still active).

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"{header(f'{BOT_NAME} — Commands')}\n\n"
        "Choose a category:"
    )
    await update.message.reply_text(
        text,
        reply_markup=_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    # Do NOT auto-delete; user needs to interact with buttons.


# ── Callback: category buttons ────────────────────────────────────────────────
# Callbacks edit the existing message — no new message sent, no auto-delete needed.

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "help_moderation"

    if data == "help_main":
        await query.edit_message_text(
            "👋 <b>Choose a category:</b>",
            reply_markup=_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    key = data.replace("help_", "", 1)
    cat_text = _CAT.get(key)
    if not cat_text:
        await query.answer("Unknown category.", show_alert=True)
        return

    await query.edit_message_text(
        cat_text,
        reply_markup=_back_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ── /ping ─────────────────────────────────────────────────────────────────────

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    t0 = time.monotonic()
    sent = await update.message.reply_text(bold("Pinging…"), parse_mode=ParseMode.HTML)
    latency = (time.monotonic() - t0) * 1000
    await sent.edit_text(
        f"🏓 {bold('Pong!')}\n{info_line('Latency', f'{latency:.2f} ms')}",
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(_delete_later(update.message, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(sent, AUTO_DELETE_DELAY))


# ── /stats ────────────────────────────────────────────────────────────────────

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_count = await db.count_chats()
    await send_and_delete(
        update.message,
        f"{header('Bot Statistics')}\n\n"
        f"{info_line('Version', VERSION)}\n"
        f"{info_line('Groups served', str(chat_count))}\n"
        f"{info_line('Status', 'Online ✅')}",
        parse_mode=ParseMode.HTML,
    )


# ── /report ───────────────────────────────────────────────────────────────────

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg.reply_to_message:
        await send_and_delete(
            msg, error("Reply to the message you want to report."), parse_mode=ParseMode.HTML
        )
        return
    reported = msg.reply_to_message.from_user
    admins = await chat.get_administrators()
    admin_mentions = " ".join(
        f'<a href="tg://user?id={a.user.id}">⚠️</a>'
        for a in admins if not a.user.is_bot
    )
    reason = " ".join(context.args) if context.args else "No reason given"
    sent = await chat.send_message(
        f"{bold('⚠️ Report')}\n\n"
        f"{info_line('Reported', mention(reported.full_name, reported.id))}\n"
        f"{info_line('By', mention(user.full_name, user.id))}\n"
        f"{info_line('Reason', reason)}\n\n"
        f"{italic('Admins notified:')} {admin_mentions}",
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(_delete_later(msg, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(sent, AUTO_DELETE_DELAY))


# ── /broadcast ────────────────────────────────────────────────────────────────

@owner_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    msg = update.effective_message
    if not args and not msg.reply_to_message:
        await send_and_delete(
            msg,
            error("Usage: /broadcast <message> OR reply to a message with /broadcast"),
            parse_mode=ParseMode.HTML,
        )
        return
    text = " ".join(args) if args else (msg.reply_to_message.text or "")
    if not text:
        await send_and_delete(msg, error("No text to broadcast."), parse_mode=ParseMode.HTML)
        return

    db_inst = db.get_db()
    cursor = db_inst.settings.find({}, {"chat_id": 1})
    sent_count, failed = 0, 0
    async for doc in cursor:
        try:
            await context.bot.send_message(
                doc["chat_id"],
                f"{header('📢 Broadcast')}\n\n{text}",
                parse_mode=ParseMode.HTML,
            )
            sent_count += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await send_and_delete(
        msg,
        success(
            f"Broadcast complete.\n"
            f"{info_line('Sent', str(sent_count))}\n"
            f"{info_line('Failed', str(failed))}"
        ),
        parse_mode=ParseMode.HTML,
    )


# ── /slowmode ─────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    chat = update.effective_chat
    msg = update.effective_message
    if not args or not args[0].isdigit():
        await send_and_delete(
            msg,
            error("Usage: /slowmode <seconds> (0 to disable)"),
            parse_mode=ParseMode.HTML,
        )
        return
    secs = int(args[0])
    try:
        await context.bot.set_chat_slow_mode_delay(chat.id, secs)
        text = success("Slow mode disabled.") if secs == 0 else success(
            f"Slow mode set to {bold(str(secs))} seconds."
        )
        await send_and_delete(msg, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /setdesc ──────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def setdesc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    desc = " ".join(context.args or [])
    msg = update.effective_message
    try:
        await context.bot.set_chat_description(update.effective_chat.id, desc)
        await send_and_delete(
            msg, success("Group description updated."), parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /settitle ─────────────────────────────────────────────────────────────────

@admin_only
@bot_admin_required
async def settitle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    msg = update.effective_message
    if not args:
        await send_and_delete(
            msg, error("Usage: /settitle <new title>"), parse_mode=ParseMode.HTML
        )
        return
    new_title = " ".join(args)
    try:
        await context.bot.set_chat_title(update.effective_chat.id, new_title)
        await send_and_delete(
            msg,
            success(f"Group title changed to {bold(new_title)}."),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)


# ── /captcha ──────────────────────────────────────────────────────────────────

@admin_only
async def captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    current = await db.get_captcha(chat.id)
    new_val = not current
    await db.set_captcha(chat.id, new_val)
    state = bold("ENABLED ✅") if new_val else bold("DISABLED ❌")
    await send_and_delete(
        update.effective_message,
        success(f"Captcha for new members: {state}"),
        parse_mode=ParseMode.HTML,
    )


# ── /antispam ─────────────────────────────────────────────────────────────────

_antispam_cache: dict[int, bool] = {}


@admin_only
async def antispam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    _antispam_cache[chat.id] = not _antispam_cache.get(chat.id, False)
    state = bold("ENABLED ✅") if _antispam_cache[chat.id] else bold("DISABLED ❌")
    await send_and_delete(
        update.effective_message,
        success(f"Anti-spam: {state}"),
        parse_mode=ParseMode.HTML,
    )


# ── /stickerban ───────────────────────────────────────────────────────────────

_sticker_ban_cache: dict[int, bool] = {}


@admin_only
@bot_admin_required
async def stickerban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    _sticker_ban_cache[chat.id] = not _sticker_ban_cache.get(chat.id, False)
    state = bold("ENABLED ✅") if _sticker_ban_cache[chat.id] else bold("DISABLED ❌")
    await send_and_delete(
        update.effective_message,
        success(f"Sticker ban: {state}\n{italic('Stickers will be auto-deleted.')}"),
        parse_mode=ParseMode.HTML,
    )


# ── /nightmode ────────────────────────────────────────────────────────────────

_night_mode_cache: dict[int, bool] = {}


@admin_only
@bot_admin_required
async def nightmode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    _night_mode_cache[chat.id] = not _night_mode_cache.get(chat.id, False)
    if _night_mode_cache[chat.id]:
        await chat.set_permissions(ChatPermissions(can_send_messages=False))
        await send_and_delete(
            update.effective_message,
            warn_msg("Night mode ON — chat is locked."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await chat.set_permissions(ChatPermissions(
            can_send_messages=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True,
            can_invite_users=True, can_send_audios=True,
            can_send_documents=True, can_send_photos=True,
            can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True,
        ))
        await send_and_delete(
            update.effective_message,
            success("Night mode OFF — chat is now open."),
            parse_mode=ParseMode.HTML,
        )


# ── register ──────────────────────────────────────────────────────────────────

def register(app) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(help_callback, pattern=r"^help_"))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("slowmode", slowmode))
    app.add_handler(CommandHandler("setdesc", setdesc))
    app.add_handler(CommandHandler("settitle", settitle))
    app.add_handler(CommandHandler("captcha", captcha))
    app.add_handler(CommandHandler("antispam", antispam))
    app.add_handler(CommandHandler("stickerban", stickerban))
    app.add_handler(CommandHandler("nightmode", nightmode))
