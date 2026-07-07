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
  9.  /post        — compose announcement with inline buttons (conversation)
"""
from __future__ import annotations
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
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

_FLOOD_DELAY = 0.05          # seconds between bulk sends (Telegram flood control)

# ConversationHandler states
_POST_TEXT, _POST_BUTTONS, _POST_TARGET = range(3)


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
# 9. /post — compose announcement with inline buttons (3-step conversation)
#
#   Step 1: owner sends the announcement text
#   Step 2: owner sends button definitions  (Label | URL, one per line)
#           or /skip to omit buttons
#   Step 3: owner specifies target: all | group <id> | user <id>
#   /cancel at any step aborts.
# ═══════════════════════════════════════════════════════════════════════════════

@owner_only
async def _post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    # Clear any leftover state from a previous incomplete session
    context.user_data.pop("post_text", None)
    context.user_data.pop("post_buttons", None)
    prompt = await msg.reply_text(
        f"{header('POST ANNOUNCEMENT')}\n\n"
        f"📝 {bold('STEP 1 / 3')} — Send the announcement text.\n\n"
        f"{italic('Type /cancel to abort.')}",
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(_delete_later(msg, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(prompt, AUTO_DELETE_DELAY))
    return _POST_TEXT


async def _post_got_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    context.user_data["post_text"] = msg.text or ""
    prompt = await msg.reply_text(
        f"{header('POST ANNOUNCEMENT')}\n\n"
        f"🔘 {bold('STEP 2 / 3')} — Add inline buttons (optional).\n\n"
        f"Format one button per line:\n"
        f"{mono('Button Label | https://example.com')}\n\n"
        f"{italic('Send /skip to add no buttons.')}",
        parse_mode=ParseMode.HTML,
    )
    asyncio.create_task(_delete_later(msg, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(prompt, AUTO_DELETE_DELAY))
    return _POST_BUTTONS


def _target_prompt() -> str:
    return (
        f"{header('POST ANNOUNCEMENT')}\n\n"
        f"📡 {bold('STEP 3 / 3')} — Where to send?\n\n"
        f"  {mono('all')}             → every registered group\n"
        f"  {mono('group <id>')}     → one specific group\n"
        f"  {mono('user <id>')}      → one user (DM)\n\n"
        f"{italic('Or /cancel to abort.')}"
    )


async def _post_skip_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    context.user_data["post_buttons"] = []
    prompt = await msg.reply_text(_target_prompt(), parse_mode=ParseMode.HTML)
    asyncio.create_task(_delete_later(msg, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(prompt, AUTO_DELETE_DELAY))
    return _POST_TARGET


async def _post_got_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg     = update.effective_message
    buttons: list[list[InlineKeyboardButton]] = []
    if msg.text:
        for line in msg.text.strip().splitlines():
            if "|" in line:
                label, _, url = line.partition("|")
                label = label.strip()
                url   = url.strip()
                # Accept any non-empty URL; Telegram validates on send
                if label and url:
                    buttons.append([InlineKeyboardButton(label, url=url)])
    context.user_data["post_buttons"] = buttons
    prompt = await msg.reply_text(_target_prompt(), parse_mode=ParseMode.HTML)
    asyncio.create_task(_delete_later(msg, AUTO_DELETE_DELAY))
    asyncio.create_task(_delete_later(prompt, AUTO_DELETE_DELAY))
    return _POST_TARGET


async def _post_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg       = update.effective_message
    raw       = (msg.text or "").strip()
    parts     = raw.split()
    post_text = context.user_data.get("post_text", "")
    btn_rows  = context.user_data.get("post_buttons", [])
    markup    = InlineKeyboardMarkup(btn_rows) if btn_rows else None
    _db       = db.get_db()

    if not parts:
        await send_and_delete(
            msg,
            error("Specify target: all | group &lt;id&gt; | user &lt;id&gt;"),
            parse_mode=ParseMode.HTML,
        )
        return _POST_TARGET  # stay in this state; let owner retry

    mode = parts[0].lower()

    if mode == "all":
        sent = failed = 0
        async for doc in _db.settings.find({}, {"chat_id": 1}):
            try:
                await context.bot.send_message(
                    doc["chat_id"], post_text,
                    parse_mode=ParseMode.HTML, reply_markup=markup,
                )
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(_FLOOD_DELAY)
        await send_and_delete(
            msg,
            success(
                f"Post sent.\n"
                f"{info_line('Sent', str(sent))}\n"
                f"{info_line('Failed', str(failed))}"
            ),
            parse_mode=ParseMode.HTML,
        )

    elif mode == "group" and len(parts) >= 2 and parts[1].lstrip("-").isdigit():
        cid = int(parts[1])
        try:
            await context.bot.send_message(
                cid, post_text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            await send_and_delete(
                msg,
                success(f"Post sent to group {mono(str(cid))}."),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)

    elif mode == "user" and len(parts) >= 2 and parts[1].lstrip("-").isdigit():
        uid = int(parts[1])
        try:
            await context.bot.send_message(
                uid, post_text, parse_mode=ParseMode.HTML, reply_markup=markup
            )
            await send_and_delete(
                msg,
                success(f"Post sent to user {mono(str(uid))}."),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await send_and_delete(msg, error(str(e)), parse_mode=ParseMode.HTML)

    else:
        await send_and_delete(
            msg,
            error("Invalid target. Use: all | group &lt;id&gt; | user &lt;id&gt;"),
            parse_mode=ParseMode.HTML,
        )
        return _POST_TARGET  # stay — let owner correct the input

    # Success — clean up and end conversation
    context.user_data.pop("post_text", None)
    context.user_data.pop("post_buttons", None)
    return ConversationHandler.END


async def _post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.effective_message
    context.user_data.pop("post_text", None)
    context.user_data.pop("post_buttons", None)
    await send_and_delete(msg, error("Post cancelled."), parse_mode=ParseMode.HTML)
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

    # /post — 3-step ConversationHandler
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("post", _post_start)],
            states={
                _POST_TEXT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, _post_got_text
                    ),
                ],
                _POST_BUTTONS: [
                    CommandHandler("skip", _post_skip_buttons),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, _post_got_buttons
                    ),
                ],
                _POST_TARGET: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, _post_send
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", _post_cancel)],
        )
    )
