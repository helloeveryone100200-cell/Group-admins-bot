"""
Owner Panel commands — all protected by @owner_only.

Build order (one command verified before the next):
  1.  /status      — system status (users & groups counts)
  2.  /listusers   — total registered user count
  3.  /listgroups  — list all registered groups (≤40 shown)
  4.  /blockuser   — block a user globally
  5.  /unblockuser — unblock a user
  6.  /blockgroup  — block a group and leave it
  7.  /unblockgroup — unblock a group
  8.  /broadcast   — all | group <id> | user <id>
  9.  /post        — up-to-5-button announcement + duration timer + confirm
"""
from __future__ import annotations
import asyncio
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

import database as db
from config import OWNER_IDS
from helpers.decorators import owner_only
from helpers.formatting import bold, mono, header, info_line, success, error, italic
from helpers.utils import send_and_delete, AUTO_DELETE_DELAY, _delete_later

_FLOOD_DELAY  = 0.05   # seconds between bulk sends (Telegram flood control)
_MAX_BUTTONS  = 5      # maximum inline buttons per /post

# /post ConversationHandler states
_POST_TEXT, _POST_BTN_NAME, _POST_BTN_URL, _POST_DURATION, _POST_CONFIRM, _POST_GROUP = range(6)

# Duration options: key → (human label, seconds)
_DURATIONS: dict[str, tuple[str, int]] = {
    "5m":  ("5 Minutes",   5 * 60),
    "15m": ("15 Minutes", 15 * 60),
    "30m": ("30 Minutes", 30 * 60),
    "1h":  ("1 Hour",     60 * 60),
    "1d":  ("1 Day",      24 * 60 * 60),
    "3d":  ("3 Days",  3 * 24 * 60 * 60),
    "1w":  ("1 Week",  7 * 24 * 60 * 60),
}

_POST_UD_KEYS = (
    "post_text", "post_buttons", "post_btn_name",
    "post_dur_key", "post_dur_secs", "post_dur_label",
    "post_target_chat", "post_target_title",
    "post_group_map",     # dict[chat_id → title] snapshotted when picker is shown
    "post_msg_cleanup",   # list[(chat_id, msg_id)] — bulk-deleted on exit
)


def _duration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5 Minutes",  callback_data="post_dur:5m"),
            InlineKeyboardButton("15 Minutes", callback_data="post_dur:15m"),
            InlineKeyboardButton("30 Minutes", callback_data="post_dur:30m"),
        ],
        [
            InlineKeyboardButton("1 Hour", callback_data="post_dur:1h"),
            InlineKeyboardButton("1 Day",  callback_data="post_dur:1d"),
            InlineKeyboardButton("3 Days", callback_data="post_dur:3d"),
        ],
        [
            InlineKeyboardButton("1 Week", callback_data="post_dur:1w"),
        ],
    ])


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ CONFIRM & SEND",  callback_data="post_confirm"),
            InlineKeyboardButton("❌ CANCEL",           callback_data="post_cancel_confirm"),
        ]
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# 1. /status — SYSTEM STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    _db  = db.get_db()
    total_groups = await _db.settings.count_documents({})
    total_users  = await db.count_users()
    blk_users    = await db.count_blocked_users()
    blk_groups   = await db.count_blocked_groups()
    text = (
        f"{header('SYSTEM STATUS')}\n\n"
        f"{info_line('Total Groups',   str(total_groups))}\n"
        f"{info_line('Total Users',    str(total_users))}\n"
        f"{info_line('Blocked Users',  str(blk_users))}\n"
        f"{info_line('Blocked Groups', str(blk_groups))}\n"
        f"{info_line('Bot Status',     'Online ✅')}"
    )
    await send_and_delete(msg, text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. /listusers — TOTAL USER COUNT
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg   = update.effective_message
    total = await db.count_users()
    await send_and_delete(
        msg,
        f"{header('USER COUNT')}\n\n"
        f"{info_line('Total Registered Users', str(total))}",
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. /listgroups — ALL REGISTERED GROUPS
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg    = update.effective_message
    groups = await db.get_all_groups()
    total  = len(groups)
    if not groups:
        await send_and_delete(
            msg, error("No groups registered yet."), parse_mode=ParseMode.HTML
        )
        return
    lines = [
        header("ALL GROUPS"),
        "",
        f"{bold('Total:')} {mono(str(total))}",
        "",
    ]
    for g in groups[:40]:
        title   = g.get("title") or "Unknown"
        chat_id = g.get("chat_id", "?")
        lines.append(f"  • {bold(title)} {mono(str(chat_id))}")
    if total > 40:
        lines.append(f"\n{italic(f'… and {total - 40} more.')}")
    text = "\n".join(lines)
    # Telegram hard-caps at 4096 chars; guard before sending
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    await send_and_delete(msg, text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. /blockuser <id>
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def blockuser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await send_and_delete(
            msg,
            f"{error('Usage:')} /blockuser &lt;user_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    uid = int(args[0])
    if uid in OWNER_IDS:
        await send_and_delete(
            msg, error("Cannot block a bot owner."), parse_mode=ParseMode.HTML
        )
        return
    await db.block_user(uid)
    await send_and_delete(
        msg,
        success(f"User {mono(str(uid))} blocked globally."),
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. /unblockuser <id>
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def unblockuser(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await send_and_delete(
            msg,
            f"{error('Usage:')} /unblockuser &lt;user_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    uid     = int(args[0])
    removed = await db.unblock_user(uid)
    if removed:
        await send_and_delete(
            msg,
            success(f"User {mono(str(uid))} unblocked."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await send_and_delete(
            msg,
            error(f"User {mono(str(uid))} is not in the blocklist."),
            parse_mode=ParseMode.HTML,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. /blockgroup <id>
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def blockgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await send_and_delete(
            msg,
            f"{error('Usage:')} /blockgroup &lt;chat_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    cid = int(args[0])
    # Try fetching the group title for a friendlier DB record
    try:
        chat_obj = await context.bot.get_chat(cid)
        title    = chat_obj.title or str(cid)
    except Exception:
        title = str(cid)
    await db.block_group(cid, title)
    # Attempt to leave the group
    try:
        await context.bot.leave_chat(cid)
        note = " Bot has left the group."
    except Exception:
        note = " (Could not leave — already removed or invalid ID.)"
    await send_and_delete(
        msg,
        success(f"Group {mono(str(cid))} blocked.{note}"),
        parse_mode=ParseMode.HTML,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 7. /unblockgroup <id>
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def unblockgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await send_and_delete(
            msg,
            f"{error('Usage:')} /unblockgroup &lt;chat_id&gt;",
            parse_mode=ParseMode.HTML,
        )
        return
    cid     = int(args[0])
    removed = await db.unblock_group(cid)
    if removed:
        await send_and_delete(
            msg,
            success(f"Group {mono(str(cid))} unblocked."),
            parse_mode=ParseMode.HTML,
        )
    else:
        await send_and_delete(
            msg,
            error(f"Group {mono(str(cid))} is not in the blocklist."),
            parse_mode=ParseMode.HTML,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. /broadcast  all <text>
#                group <id> <text>
#                user  <id> <text>
# ═══════════════════════════════════════════════════════════════════════════════

_BC_USAGE = (
    f"{error('Usage:')}\n"
    "/broadcast all &lt;text&gt;\n"
    "/broadcast group &lt;id&gt; &lt;text&gt;\n"
    "/broadcast user &lt;id&gt; &lt;text&gt;"
)


@owner_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg  = update.effective_message
    args = context.args or []
    if not args:
        await send_and_delete(msg, _BC_USAGE, parse_mode=ParseMode.HTML)
        return

    mode = args[0].lower()
    _db  = db.get_db()

    # ── /broadcast all <text> ─────────────────────────────────────────────────
    if mode == "all":
        text = " ".join(args[1:]).strip()
        if not text:
            await send_and_delete(
                msg, error("Message text cannot be empty."), parse_mode=ParseMode.HTML
            )
            return
        sent = failed = 0
        payload = f"📢 {bold('BROADCAST')}\n\n{text}"
        # Groups
        async for doc in _db.settings.find({}, {"chat_id": 1}):
            try:
                await context.bot.send_message(
                    doc["chat_id"], payload, parse_mode=ParseMode.HTML
                )
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(_FLOOD_DELAY)
        # Registered users (DM)
        async for doc in _db.users.find({}, {"user_id": 1}):
            try:
                await context.bot.send_message(
                    doc["user_id"], payload, parse_mode=ParseMode.HTML
                )
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(_FLOOD_DELAY)
        await send_and_delete(
            msg,
            success(
                f"Broadcast done.\n"
                f"{info_line('Sent', str(sent))}\n"
                f"{info_line('Failed', str(failed))}"
            ),
            parse_mode=ParseMode.HTML,
        )

    # ── /broadcast group <id> <text> ─────────────────────────────────────────
    elif mode == "group":
        if len(args) < 3 or not args[1].lstrip("-").isdigit():
            await send_and_delete(msg, _BC_USAGE, parse_mode=ParseMode.HTML)
            return
        cid  = int(args[1])
        text = " ".join(args[2:]).strip()
        if not text:
            await send_and_delete(
                msg, error("Message text cannot be empty."), parse_mode=ParseMode.HTML
            )
            return
        try:
            await context.bot.send_message(
                cid,
                f"📢 {bold('MESSAGE FROM OWNER')}\n\n{text}",
                parse_mode=ParseMode.HTML,
            )
            await send_and_delete(
                msg,
                success(f"Message sent to group {mono(str(cid))}."),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)

    # ── /broadcast user <id> <text> ──────────────────────────────────────────
    elif mode == "user":
        if len(args) < 3 or not args[1].lstrip("-").isdigit():
            await send_and_delete(msg, _BC_USAGE, parse_mode=ParseMode.HTML)
            return
        uid  = int(args[1])
        text = " ".join(args[2:]).strip()
        if not text:
            await send_and_delete(
                msg, error("Message text cannot be empty."), parse_mode=ParseMode.HTML
            )
            return
        try:
            await context.bot.send_message(
                uid,
                f"📢 {bold('MESSAGE FROM OWNER')}\n\n{text}",
                parse_mode=ParseMode.HTML,
            )
            await send_and_delete(
                msg,
                success(f"Message sent to user {mono(str(uid))}."),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)

    else:
        await send_and_delete(msg, _BC_USAGE, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. /post — multi-button announcement with timer + group picker + confirm
#
#   Step 1   → text
#   Step 2+  → button loop: NAME → URL (up to _MAX_BUTTONS)
#              [✅ Done] inline button exits the loop early (≥1 button collected)
#   Step N   → duration inline keyboard
#   Step N+1 → group picker (inline keyboard built from DB — warns if no groups)
#   Step N+2 → confirm keyboard → sends post + schedules auto-delete
#   All conversation messages are bulk-deleted when the flow ends.
# ═══════════════════════════════════════════════════════════════════════════════

_MAX_GROUPS_SHOWN = 20   # cap group picker to avoid oversized keyboards

def _url_from_input(raw: str) -> str:
    """Normalise @username / bare username / t.me/... → full URL; preserve https://."""
    raw   = raw.strip()
    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return raw
    if lower.startswith("t.me/"):
        return f"https://{raw}"
    return f"https://t.me/{raw.lstrip('@')}"


def _clear_post_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for k in _POST_UD_KEYS:
        context.user_data.pop(k, None)


def _track_msgs(context: ContextTypes.DEFAULT_TYPE, *msgs) -> None:
    """Register messages for bulk deletion when the /post flow ends."""
    cleanup: list = context.user_data.setdefault("post_msg_cleanup", [])
    for m in msgs:
        if m is not None:
            cleanup.append((m.chat_id, m.message_id))


async def _cleanup_conversation(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete every tracked /post conversation message immediately."""
    for chat_id, msg_id in context.user_data.pop("post_msg_cleanup", []):
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass   # already deleted or no permission — silently skip


async def _auto_delete_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    """PTB job_queue callback — deletes the timed post after its duration expires."""
    data = context.job.data
    try:
        await context.bot.delete_message(data["chat_id"], data["message_id"])
    except Exception:
        pass


def _done_keyboard() -> InlineKeyboardMarkup:
    """[✅ Done] button shown on every 'add another button' prompt."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Done — Finish Adding Buttons", callback_data="post_done"),
    ]])


# ── Step 1: /post entry ───────────────────────────────────────────────────────

@owner_only
async def _post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg  = update.effective_message
    chat = update.effective_chat
    _clear_post_data(context)
    context.user_data["post_buttons"]     = []
    context.user_data["post_msg_cleanup"] = []

    prompt = await msg.reply_text(
        f"{bold('📝 CREATE A POST')}\n\n"
        f"TYPE YOUR POST MESSAGE BELOW.\n\n"
        f"{italic('SEND /CANCEL TO STOP AT ANY TIME.')}",
        parse_mode=ParseMode.HTML,
    )
    _track_msgs(context, msg, prompt)
    return _POST_TEXT


# ── Step 2: receive text → ask Button 1 name ─────────────────────────────────

async def _post_got_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    context.user_data["post_text"] = msg.text or ""

    prompt = await msg.reply_text(
        f"{bold('🔘 BUTTON 1 — NAME')}\n\n"
        f"TYPE THE BUTTON LABEL (E.G. CONTACT ADMIN)\n\n"
        f"{italic(f'YOU CAN ADD 1 TO {_MAX_BUTTONS} BUTTONS IN TOTAL.')}",
        parse_mode=ParseMode.HTML,
    )
    _track_msgs(context, msg, prompt)
    return _POST_BTN_NAME


# ── Step 3a: receive button name → ask URL ────────────────────────────────────

async def _post_got_btn_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg      = update.effective_message
    btn_name = (msg.text or "").strip()

    if not btn_name:
        prompt = await msg.reply_text(
            error("Button label cannot be empty. Try again."),
            parse_mode=ParseMode.HTML,
        )
        _track_msgs(context, msg, prompt)
        return _POST_BTN_NAME

    context.user_data["post_btn_name"] = btn_name
    btn_num = len(context.user_data.get("post_buttons", [])) + 1

    prompt = await msg.reply_text(
        f"{bold(f'🔗 BUTTON {btn_num} — URL')}\n\n"
        f"ENTER A URL OR @USERNAME\n"
        f"{italic('E.G. HTTPS://T.ME/ADMIN OR @ADMIN')}",
        parse_mode=ParseMode.HTML,
    )
    _track_msgs(context, msg, prompt)
    return _POST_BTN_URL


# ── Step 3b: receive URL → save button → next or duration ────────────────────

async def _post_got_btn_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg     = update.effective_message
    raw_url = (msg.text or "").strip()

    if not raw_url:
        prompt = await msg.reply_text(
            error("URL cannot be empty. Try again or /cancel."),
            parse_mode=ParseMode.HTML,
        )
        _track_msgs(context, msg, prompt)
        return _POST_BTN_URL

    url      = _url_from_input(raw_url)
    btn_name = context.user_data.get("post_btn_name", "Button")
    buttons  = context.user_data.setdefault("post_buttons", [])
    buttons.append([InlineKeyboardButton(btn_name, url=url)])
    btn_count = len(buttons)
    _track_msgs(context, msg)

    if btn_count >= _MAX_BUTTONS:
        # Hard limit reached — proceed directly to duration
        prompt = await msg.reply_text(
            f"{bold(f'✅ BUTTON {btn_count} ADDED')}\n"
            f"{italic(f'({_MAX_BUTTONS}/{_MAX_BUTTONS} — MAXIMUM REACHED)')}",
            parse_mode=ParseMode.HTML,
        )
        _track_msgs(context, prompt)
        return await _ask_duration(msg, context)

    # Prompt for next button — include [Done] inline button
    next_num = btn_count + 1
    prompt = await msg.reply_text(
        f"{bold(f'✅ BUTTON {btn_count} ADDED')}\n\n"
        f"{bold(f'🔘 BUTTON {next_num} — NAME')}\n\n"
        f"TYPE THE NEXT BUTTON LABEL\n"
        f"{italic(f'MAX {_MAX_BUTTONS} BUTTONS TOTAL')}",
        reply_markup=_done_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    _track_msgs(context, prompt)
    return _POST_BTN_NAME


# ── [Done] inline button — finish button collection early ─────────────────────

async def _post_done_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback from the [✅ Done] button shown on 'add another button' prompts."""
    query = update.callback_query
    await query.answer()
    # Remove the inline keyboard from the prompt so it looks clean
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    return await _ask_duration(query.message, context)


# ── Duration keyboard (not tracked — it becomes the confirm/success message) ──

async def _ask_duration(msg, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send the duration keyboard. This message is deliberately NOT added to the
    cleanup list — it is edited through confirm→success and deleted separately
    with a short delay so the owner can read the result."""
    await msg.reply_text(
        f"{bold('⏱ HOW LONG TO KEEP THIS POST?')}\n\n"
        f"SELECT A DURATION BELOW.",
        reply_markup=_duration_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return _POST_DURATION


def _build_group_keyboard(groups: list[dict]) -> InlineKeyboardMarkup:
    """Build a 2-column inline keyboard from a list of {chat_id, title} dicts."""
    buttons = [
        InlineKeyboardButton(
            g.get("title", str(g["chat_id"]))[:32],
            callback_data=f"post_group:{g['chat_id']}",
        )
        for g in groups[:_MAX_GROUPS_SHOWN]
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


async def _post_got_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    key = query.data.split(":", 1)[1]   # "post_dur:5m" → "5m"
    if key not in _DURATIONS:
        return _POST_DURATION            # unknown callback — ignore

    label, seconds = _DURATIONS[key]
    context.user_data["post_dur_key"]   = key
    context.user_data["post_dur_secs"]  = seconds
    context.user_data["post_dur_label"] = label

    # Fetch groups the bot is a member of
    groups = await db.get_all_groups()
    if not groups:
        await query.edit_message_text(
            f"{bold('❌ NO GROUPS FOUND')}\n\n"
            f"BOT HAS NOT BEEN ADDED TO ANY GROUPS YET.\n\n"
            f"{italic('ADD THE BOT TO A GROUP FIRST, THEN TRY /POST AGAIN.')}",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(_delete_later(query.message, 10))
        await _cleanup_conversation(context)
        _clear_post_data(context)
        return ConversationHandler.END

    # Snapshot the group map so _post_got_group can validate without a second DB hit
    context.user_data["post_group_map"] = {
        g["chat_id"]: g.get("title", str(g["chat_id"]))
        for g in groups[:_MAX_GROUPS_SHOWN]
    }

    note = (
        f"\n{italic(f'(SHOWING FIRST {_MAX_GROUPS_SHOWN} OF {len(groups)})')}"
        if len(groups) > _MAX_GROUPS_SHOWN else ""
    )
    await query.edit_message_text(
        f"{bold('📡 SELECT TARGET GROUP')}\n\n"
        f"CHOOSE WHICH GROUP TO SEND THIS POST TO.{note}",
        reply_markup=_build_group_keyboard(groups),
        parse_mode=ParseMode.HTML,
    )
    return _POST_GROUP


async def _post_got_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Owner tapped a group button — validate, store target, show confirm screen."""
    query = update.callback_query

    try:
        target_chat = int(query.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.answer()
        return _POST_GROUP   # malformed callback — ignore

    # Validate against the snapshot taken when the picker was rendered
    group_map: dict = context.user_data.get("post_group_map", {})
    if target_chat not in group_map:
        # Stale selection — the group was removed from DB between picker render & tap.
        # Answer exactly once here (with the alert) instead of also answering above.
        await query.answer(
            "⚠️ That group is no longer available. Please select another.",
            show_alert=True,
        )
        return _POST_GROUP   # stay on picker; owner must tap a valid group

    await query.answer()
    group_title = group_map[target_chat]
    context.user_data["post_target_chat"]  = target_chat
    context.user_data["post_target_title"] = group_title

    post_text = context.user_data.get("post_text", "")
    btn_count = len(context.user_data.get("post_buttons", []))
    dur_label = context.user_data.get("post_dur_label", "?")
    preview   = escape(post_text[:80]) + ("…" if len(post_text) > 80 else "")

    await query.edit_message_text(
        f"{bold('📋 CONFIRM POST')}\n\n"
        f"💬 {bold('Message:')}  {preview}\n"
        f"🔘 {bold('Buttons:')}  {btn_count}\n"
        f"⏱ {bold('Duration:')} {dur_label}\n"
        f"📡 {bold('Group:')}    {escape(group_title)}\n\n"
        f"PRESS CONFIRM TO SEND.",
        reply_markup=_confirm_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return _POST_CONFIRM


# ── Confirm ───────────────────────────────────────────────────────────────────

async def _post_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    post_text   = context.user_data.get("post_text", "")
    buttons     = context.user_data.get("post_buttons", [])
    dur_secs    = context.user_data.get("post_dur_secs",  300)
    dur_label   = context.user_data.get("post_dur_label", "5 Minutes")
    target_chat = context.user_data.get("post_target_chat")
    group_title = context.user_data.get("post_target_title", "this chat")
    markup      = InlineKeyboardMarkup(buttons) if buttons else None

    try:
        sent = await context.bot.send_message(
            target_chat,
            post_text,        # plain text — no parse_mode, so <>&  are safe
            reply_markup=markup,
        )
        # Schedule auto-delete of the post — prefer PTB job_queue, fall back to asyncio
        if context.job_queue is not None:
            context.job_queue.run_once(
                _auto_delete_post,
                when=dur_secs,
                data={"chat_id": target_chat, "message_id": sent.message_id},
                name=f"post_del_{target_chat}_{sent.message_id}",
            )
        else:
            _chat_id, _msg_id, _bot = target_chat, sent.message_id, context.bot

            async def _fallback_delete() -> None:
                await asyncio.sleep(dur_secs)
                try:
                    await _bot.delete_message(_chat_id, _msg_id)
                except Exception:
                    pass

            asyncio.create_task(_fallback_delete())

        # Show success on the confirm message
        await query.edit_message_text(
            f"{bold('✅ POST SENT!')}\n"
            f"📍 GROUP: {escape(group_title)}\n"
            f"⏱ EXPIRES IN: {dur_label}",
            parse_mode=ParseMode.HTML,
        )
        # Wipe all conversation messages immediately, then remove the success notice
        await _cleanup_conversation(context)
        asyncio.create_task(_delete_later(query.message, 8))   # 8-second grace period

    except Exception as exc:
        await query.edit_message_text(
            error(escape(str(exc))), parse_mode=ParseMode.HTML
        )
        await _cleanup_conversation(context)

    _clear_post_data(context)
    return ConversationHandler.END


# ── Cancel from the confirm screen ───────────────────────────────────────────

async def _post_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await _cleanup_conversation(context)
    _clear_post_data(context)
    await query.edit_message_text(error("Post cancelled."), parse_mode=ParseMode.HTML)
    asyncio.create_task(_delete_later(query.message, 5))
    return ConversationHandler.END


# ── /cancel fallback (any text step) ─────────────────────────────────────────

async def _post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    _track_msgs(context, msg)          # wipe the /cancel command with everything else
    await _cleanup_conversation(context)
    _clear_post_data(context)
    # Send WITHOUT replying — msg was just deleted, so reply_to would 404 in groups
    reply = await context.bot.send_message(
        msg.chat_id,
        error("Post cancelled."),
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(_delete_later(reply, 5))
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
# Register all owner handlers
# ═══════════════════════════════════════════════════════════════════════════════

def register(app) -> None:
    app.add_handler(CommandHandler("status",       status))
    app.add_handler(CommandHandler("listusers",    listusers))
    app.add_handler(CommandHandler("listgroups",   listgroups))
    app.add_handler(CommandHandler("blockuser",    blockuser))
    app.add_handler(CommandHandler("unblockuser",  unblockuser))
    app.add_handler(CommandHandler("blockgroup",   blockgroup))
    app.add_handler(CommandHandler("unblockgroup", unblockgroup))
    app.add_handler(CommandHandler("broadcast",    broadcast))

    # /post — multi-button + duration timer + confirm + auto-cleanup
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("post", _post_start)],
            states={
                _POST_TEXT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _post_got_text),
                ],
                _POST_BTN_NAME: [
                    # [✅ Done] inline button — no typing needed to finish loop
                    CallbackQueryHandler(_post_done_buttons, pattern=r"^post_done$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _post_got_btn_name),
                ],
                _POST_BTN_URL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, _post_got_btn_url),
                ],
                _POST_DURATION: [
                    CallbackQueryHandler(_post_got_duration, pattern=r"^post_dur:"),
                ],
                _POST_GROUP: [
                    CallbackQueryHandler(_post_got_group, pattern=r"^post_group:"),
                ],
                _POST_CONFIRM: [
                    CallbackQueryHandler(_post_confirm,        pattern=r"^post_confirm$"),
                    CallbackQueryHandler(_post_cancel_confirm, pattern=r"^post_cancel_confirm$"),
                ],
            },
            fallbacks=[CommandHandler("cancel", _post_cancel)],
            # per_chat=True + per_user=True: scoped to (chat, user) pair —
            # owner's /post in group A cannot bleed into group B.
            per_chat=True,
            per_user=True,
        )
    )
