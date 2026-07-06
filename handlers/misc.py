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
        "🛡️ <b>𝗠𝗢𝗗𝗘𝗥𝗔𝗧𝗜𝗢𝗡</b>\n\n"
        "/ban — 𝗕𝗮𝗻 𝗮 𝘂𝘀𝗲𝗿\n"
        "/unban — 𝗨𝗻𝗯𝗮𝗻 𝗮 𝘂𝘀𝗲𝗿\n"
        "/tban — 𝗧𝗲𝗺𝗽 𝗯𝗮𝗻 (𝗲.𝗴. /tban @user 1h)\n"
        "/kick — 𝗞𝗶𝗰𝗸 𝗮 𝘂𝘀𝗲𝗿\n"
        "/mute — 𝗠𝘂𝘁𝗲 𝗮 𝘂𝘀𝗲𝗿\n"
        "/unmute — 𝗨𝗻𝗺𝘂𝘁𝗲 𝗮 𝘂𝘀𝗲𝗿\n"
        "/tmute — 𝗧𝗲𝗺𝗽 𝗺𝘂𝘁𝗲 (𝗲.𝗴. /tmute @user 30m)\n"
        "/promote — 𝗣𝗿𝗼𝗺𝗼𝘁𝗲 𝘁𝗼 𝗮𝗱𝗺𝗶𝗻\n"
        "/demote — 𝗥𝗲𝗺𝗼𝘃𝗲 𝗮𝗱𝗺𝗶𝗻 𝗿𝗶𝗴𝗵𝘁𝘀\n"
        "/title — 𝗦𝗲𝘁 𝗰𝘂𝘀𝘁𝗼𝗺 𝗮𝗱𝗺𝗶𝗻 𝘁𝗶𝘁𝗹𝗲\n"
        "/pin [silent] — 𝗣𝗶𝗻 𝗮 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/unpin — 𝗨𝗻𝗽𝗶𝗻 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/unpinall — 𝗨𝗻𝗽𝗶𝗻 𝗮𝗹𝗹 𝗺𝗲𝘀𝘀𝗮𝗴𝗲𝘀\n"
        "/purge — 𝗣𝘂𝗿𝗴𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲𝘀 (𝗿𝗲𝗽𝗹𝘆 𝘁𝗼 𝘀𝘁𝗮𝗿𝘁)\n"
        "/del — 𝗗𝗲𝗹𝗲𝘁𝗲 𝗮 𝘀𝗶𝗻𝗴𝗹𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲"
    ),
    "warnings": (
        "⚠️ <b>𝗪𝗔𝗥𝗡𝗜𝗡𝗚𝗦</b>\n\n"
        "/warn — 𝗪𝗮𝗿𝗻 𝗮 𝘂𝘀𝗲𝗿\n"
        "/unwarn — 𝗥𝗲𝗺𝗼𝘃𝗲 𝗹𝗮𝘀𝘁 𝘄𝗮𝗿𝗻𝗶𝗻𝗴\n"
        "/resetwarn — 𝗥𝗲𝘀𝗲𝘁 𝗮𝗹𝗹 𝘄𝗮𝗿𝗻𝗶𝗻𝗴𝘀\n"
        "/warnings — 𝗦𝗵𝗼𝘄 𝘄𝗮𝗿𝗻𝗶𝗻𝗴 𝗰𝗼𝘂𝗻𝘁\n"
        "/warnlimit — 𝗦𝗲𝘁 𝘄𝗮𝗿𝗻 𝗹𝗶𝗺𝗶𝘁 (𝗱𝗲𝗳𝗮𝘂𝗹𝘁 𝟯)\n\n"
        "<i>𝗪𝗵𝗲𝗻 𝗹𝗶𝗺𝗶𝘁 𝗶𝘀 𝗿𝗲𝗮𝗰𝗵𝗲𝗱 𝘁𝗵𝗲 𝘂𝘀𝗲𝗿 𝗶𝘀 𝗮𝘂𝘁𝗼𝗺𝗮𝘁𝗶𝗰𝗮𝗹𝗹𝘆 𝗯𝗮𝗻𝗻𝗲𝗱.</i>"
    ),
    "group_control": (
        "🔒 <b>𝗚𝗥𝗢𝗨𝗣 𝗖𝗢𝗡𝗧𝗥𝗢𝗟</b>\n\n"
        "/lock &lt;type&gt; — 𝗟𝗼𝗰𝗸 𝗮 𝗰𝗵𝗮𝘁 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻\n"
        "/unlock &lt;type&gt; — 𝗨𝗻𝗹𝗼𝗰𝗸 𝗮 𝗰𝗵𝗮𝘁 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻\n"
        "/locktypes — 𝗦𝗵𝗼𝘄 𝗮𝗹𝗹 𝗹𝗼𝗰𝗸𝗮𝗯𝗹𝗲 𝘁𝘆𝗽𝗲𝘀\n"
        "/slowmode &lt;seconds&gt; — 𝗦𝗲𝘁 𝘀𝗹𝗼𝘄 𝗺𝗼𝗱𝗲\n"
        "/nightmode — 𝗧𝗼𝗴𝗴𝗹𝗲 𝗻𝗶𝗴𝗵𝘁 𝗹𝗼𝗰𝗸\n"
        "/setdesc &lt;text&gt; — 𝗦𝗲𝘁 𝗴𝗿𝗼𝘂𝗽 𝗱𝗲𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻\n"
        "/settitle &lt;text&gt; — 𝗦𝗲𝘁 𝗴𝗿𝗼𝘂𝗽 𝘁𝗶𝘁𝗹𝗲\n"
        "/antiflood [n] — 𝗦𝗲𝘁 𝗳𝗹𝗼𝗼𝗱 𝗹𝗶𝗺𝗶𝘁\n"
        "/floodmode &lt;mode&gt; — 𝗦𝗲𝘁 𝗳𝗹𝗼𝗼𝗱 𝗮𝗰𝘁𝗶𝗼𝗻\n"
        "/blacklist [word] — 𝗩𝗶𝗲𝘄/𝗮𝗱𝗱 𝗯𝗹𝗮𝗰𝗸𝗹𝗶𝘀𝘁\n"
        "/unblacklist &lt;word&gt; — 𝗥𝗲𝗺𝗼𝘃𝗲 𝗳𝗿𝗼𝗺 𝗯𝗹𝗮𝗰𝗸𝗹𝗶𝘀𝘁\n"
        "/blmode &lt;mode&gt; — 𝗦𝗲𝘁 𝗯𝗹𝗮𝗰𝗸𝗹𝗶𝘀𝘁 𝗮𝗰𝘁𝗶𝗼𝗻"
    ),
    "settings": (
        "⚙️ <b>𝗦𝗘𝗧𝗧𝗜𝗡𝗚𝗦</b>\n\n"
        "/welcome — 𝗦𝗵𝗼𝘄 𝗰𝘂𝗿𝗿𝗲𝗻𝘁 𝘄𝗲𝗹𝗰𝗼𝗺𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/setwelcome — 𝗦𝗲𝘁 𝘄𝗲𝗹𝗰𝗼𝗺𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/clearwelcome — 𝗖𝗹𝗲𝗮𝗿 𝘄𝗲𝗹𝗰𝗼𝗺𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/goodbye — 𝗦𝗵𝗼𝘄 𝗴𝗼𝗼𝗱𝗯𝘆𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/setgoodbye — 𝗦𝗲𝘁 𝗴𝗼𝗼𝗱𝗯𝘆𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/cleargoodbye — 𝗖𝗹𝗲𝗮𝗿 𝗴𝗼𝗼𝗱𝗯𝘆𝗲 𝗺𝗲𝘀𝘀𝗮𝗴𝗲\n"
        "/rules — 𝗦𝗵𝗼𝘄 𝗴𝗿𝗼𝘂𝗽 𝗿𝘂𝗹𝗲𝘀\n"
        "/setrules — 𝗦𝗲𝘁 𝗴𝗿𝗼𝘂𝗽 𝗿𝘂𝗹𝗲𝘀\n"
        "/clearrules — 𝗖𝗹𝗲𝗮𝗿 𝗴𝗿𝗼𝘂𝗽 𝗿𝘂𝗹𝗲𝘀\n"
        "/captcha — 𝗧𝗼𝗴𝗴𝗹𝗲 𝗰𝗮𝗽𝘁𝗰𝗵𝗮 𝗳𝗼𝗿 𝗻𝗲𝘄 𝗺𝗲𝗺𝗯𝗲𝗿𝘀\n"
        "/antispam — 𝗧𝗼𝗴𝗴𝗹𝗲 𝗮𝗻𝘁𝗶-𝘀𝗽𝗮𝗺\n"
        "/stickerban — 𝗧𝗼𝗴𝗴𝗹𝗲 𝘀𝘁𝗶𝗰𝗸𝗲𝗿 𝗯𝗮𝗻\n"
        "/filter &lt;kw&gt; &lt;reply&gt; — 𝗔𝗱𝗱 𝗮𝘂𝘁𝗼-𝗿𝗲𝗽𝗹𝘆 𝗳𝗶𝗹𝘁𝗲𝗿\n"
        "/filters — 𝗟𝗶𝘀𝘁 𝗳𝗶𝗹𝘁𝗲𝗿𝘀\n"
        "/stop &lt;kw&gt; — 𝗥𝗲𝗺𝗼𝘃𝗲 𝗮 𝗳𝗶𝗹𝘁𝗲𝗿\n"
        "/stopall — 𝗥𝗲𝗺𝗼𝘃𝗲 𝗮𝗹𝗹 𝗳𝗶𝗹𝘁𝗲𝗿𝘀\n"
        "/note &lt;name&gt; &lt;text&gt; — 𝗦𝗮𝘃𝗲 𝗮 𝗻𝗼𝘁𝗲\n"
        "/get &lt;name&gt; — 𝗚𝗲𝘁 𝗮 𝗻𝗼𝘁𝗲\n"
        "/notes — 𝗟𝗶𝘀𝘁 𝗮𝗹𝗹 𝗻𝗼𝘁𝗲𝘀\n"
        "/clearnote &lt;name&gt; — 𝗗𝗲𝗹𝗲𝘁𝗲 𝗮 𝗻𝗼𝘁𝗲\n"
        "/clearallnotes — 𝗗𝗲𝗹𝗲𝘁𝗲 𝗮𝗹𝗹 𝗻𝗼𝘁𝗲𝘀"
    ),
    "scheduling": (
        "📅 <b>𝗦𝗖𝗛𝗘𝗗𝗨𝗟𝗜𝗡𝗚</b>\n\n"
        "<b>𝗔𝗗𝗗 𝗔 𝗦𝗖𝗛𝗘𝗗𝗨𝗟𝗘:</b>\n"
        "<code>/addschedule &lt;name&gt; one_time YYYY-MM-DD HH:MM &lt;msg&gt;</code>\n"
        "<code>/addschedule &lt;name&gt; always HH:MM &lt;msg&gt;</code>\n\n"
        "• <b>𝗼𝗻𝗲_𝘁𝗶𝗺𝗲</b> — 𝗙𝗶𝗿𝗲𝘀 𝗼𝗻𝗰𝗲 𝗮𝘁 𝘁𝗵𝗲 𝗴𝗶𝘃𝗲𝗻 𝗱𝗮𝘁𝗲 &amp; 𝘁𝗶𝗺𝗲, 𝘁𝗵𝗲𝗻 𝗿𝗲𝗺𝗼𝘃𝗲𝗱\n"
        "• <b>𝗮𝗹𝘄𝗮𝘆𝘀</b> — 𝗙𝗶𝗿𝗲𝘀 𝗲𝘃𝗲𝗿𝘆 𝗱𝗮𝘆 𝗮𝘁 𝘁𝗵𝗲 𝗴𝗶𝘃𝗲𝗻 𝘁𝗶𝗺𝗲\n\n"
        "/schedules — 𝗟𝗶𝘀𝘁 𝗮𝗹𝗹 𝗮𝗰𝘁𝗶𝘃𝗲 𝘀𝗰𝗵𝗲𝗱𝘂𝗹𝗲𝘀\n"
        "/delschedule &lt;id or name&gt; — 𝗗𝗲𝗹𝗲𝘁𝗲 𝗮 𝘀𝗰𝗵𝗲𝗱𝘂𝗹𝗲"
    ),
    "id_info": (
        "🆔 <b>𝗜𝗗 &amp; 𝗜𝗡𝗙𝗢</b>\n\n"
        "/id — 𝗦𝗵𝗼𝘄 𝘆𝗼𝘂𝗿 / 𝗿𝗲𝗽𝗹𝗶𝗲𝗱 𝘂𝘀𝗲𝗿'𝘀 𝗜𝗗\n"
        "/info — 𝗗𝗲𝘁𝗮𝗶𝗹𝗲𝗱 𝘂𝘀𝗲𝗿 𝗶𝗻𝗳𝗼\n"
        "/chatinfo — 𝗖𝗵𝗮𝘁 𝗶𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻\n"
        "/adminlist — 𝗟𝗶𝘀𝘁 𝗮𝗹𝗹 𝗮𝗱𝗺𝗶𝗻𝘀\n"
        "/invite — 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲 𝗶𝗻𝘃𝗶𝘁𝗲 𝗹𝗶𝗻𝗸\n"
        "/ping — 𝗖𝗵𝗲𝗰𝗸 𝗯𝗼𝘁 𝗹𝗮𝘁𝗲𝗻𝗰𝘆\n"
        "/stats — 𝗕𝗼𝘁 𝘀𝘁𝗮𝘁𝗶𝘀𝘁𝗶𝗰𝘀\n"
        "/report — 𝗥𝗲𝗽𝗼𝗿𝘁 𝗮 𝘂𝘀𝗲𝗿 𝘁𝗼 𝗮𝗱𝗺𝗶𝗻𝘀"
    ),
    "owner": (
        "👑 <b>𝗢𝗪𝗡𝗘𝗥 𝗣𝗔𝗡𝗘𝗟</b>\n\n"
        "/broadcast &lt;text&gt; — 𝗦𝗲𝗻𝗱 𝗺𝗲𝘀𝘀𝗮𝗴𝗲 𝘁𝗼 𝗮𝗹𝗹 𝗴𝗿𝗼𝘂𝗽𝘀\n"
        "/stats — 𝗩𝗶𝗲𝘄 𝗯𝗼𝘁 𝘀𝘁𝗮𝘁𝗶𝘀𝘁𝗶𝗰𝘀\n\n"
        "<i>𝗢𝗻𝗹𝘆 𝗮𝗰𝗰𝗲𝘀𝘀𝗶𝗯𝗹𝗲 𝗯𝘆 𝗯𝗼𝘁 𝗼𝘄𝗻𝗲𝗿𝘀.</i>"
    ),
}

# ── Inline keyboard builders ──────────────────────────────────────────────────

def _main_keyboard(bot_username: str = "", is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🛡️ 𝗠𝗢𝗗𝗘𝗥𝗔𝗧𝗜𝗢𝗡",   callback_data="help_moderation"),
            InlineKeyboardButton("⚠️ 𝗪𝗔𝗥𝗡𝗜𝗡𝗚𝗦",     callback_data="help_warnings"),
        ],
        [
            InlineKeyboardButton("🔒 𝗚𝗥𝗢𝗨𝗣 𝗖𝗢𝗡𝗧𝗥𝗢𝗟", callback_data="help_group_control"),
            InlineKeyboardButton("⚙️ 𝗦𝗘𝗧𝗧𝗜𝗡𝗚𝗦",      callback_data="help_settings"),
        ],
        [
            InlineKeyboardButton("📅 𝗦𝗖𝗛𝗘𝗗𝗨𝗟𝗜𝗡𝗚",    callback_data="help_scheduling"),
            InlineKeyboardButton("🆔 𝗜𝗗 & 𝗜𝗡𝗙𝗢",     callback_data="help_id_info"),
        ],
    ]
    # Owner Panel row — visible only to bot owners
    if is_owner:
        rows.append([
            InlineKeyboardButton("👑 𝗢𝗪𝗡𝗘𝗥 𝗣𝗔𝗡𝗘𝗟", callback_data="help_owner"),
        ])
    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ 𝗔𝗗𝗗 𝗧𝗢 𝗚𝗥𝗢𝗨𝗣",
                url=f"https://t.me/{bot_username}?startgroup=true",
            ),
            InlineKeyboardButton(
                "📤 𝗦𝗛𝗔𝗥𝗘",
                url=(
                    f"https://t.me/share/url"
                    f"?url=https://t.me/{bot_username}"
                    f"&text=Add%20this%20group%20management%20bot%20to%20your%20group%21"
                ),
            ),
        ])
    return InlineKeyboardMarkup(rows)


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("« 𝗕𝗔𝗖𝗞", callback_data="help_main"),
    ]])


# ── /start ────────────────────────────────────────────────────────────────────
# NOTE: /start welcome message is NEVER auto-deleted.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = context.bot.username or ""
    is_owner = user.id in OWNER_IDS
    text = (
        f"👋 <b>𝗛𝗘𝗟𝗟𝗢, {user.full_name}!</b>\n\n"
        f"𝗜 𝗔𝗠 𝗬𝗢𝗨𝗥 𝗚𝗥𝗢𝗨𝗣 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧 𝗕𝗢𝗧.\n"
        f"𝗖𝗛𝗢𝗢𝗦𝗘 𝗔 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬 𝗕𝗘𝗟𝗢𝗪 𝗧𝗢 𝗦𝗘𝗘 𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦."
    )
    await update.message.reply_text(
        text,
        reply_markup=_main_keyboard(username, is_owner=is_owner),
        parse_mode=ParseMode.HTML,
    )
    # Do NOT auto-delete the /start welcome message or its inline buttons.


# ── /help ─────────────────────────────────────────────────────────────────────
# NOTE: /help menu message is also NOT auto-deleted (inline buttons still active).

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.bot.username or ""
    is_owner = update.effective_user.id in OWNER_IDS
    text = (
        f"{header(f'{BOT_NAME} — Commands')}\n\n"
        "𝗖𝗛𝗢𝗢𝗦𝗘 𝗔 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬:"
    )
    await update.message.reply_text(
        text,
        reply_markup=_main_keyboard(username, is_owner=is_owner),
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
        username = context.bot.username or ""
        is_owner = query.from_user.id in OWNER_IDS
        await query.edit_message_text(
            "👋 <b>𝗖𝗛𝗢𝗢𝗦𝗘 𝗔 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬:</b>",
            reply_markup=_main_keyboard(username, is_owner=is_owner),
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
