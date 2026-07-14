"""English strings (default / fallback locale)."""

STRINGS: dict[str, str] = {
    # ── ping ──────────────────────────────────────────────────────────────────
    "ping": "🏓 <b>Pong!</b>  Latency: <b>{latency} ms</b>",

    # ── shared toggle states ──────────────────────────────────────────────────
    "enabled":  "ENABLED ✅",
    "disabled": "DISABLED ❌",

    # ── captcha ───────────────────────────────────────────────────────────────
    "captcha_toggled": "Captcha for new members: {state}",

    # ── antispam ──────────────────────────────────────────────────────────────
    "antispam_toggled": "Anti-spam: {state}",
    "antispam_warn": (
        "{name} warned for spamming identical messages. "
        "{count}/{limit} warnings."
    ),
    "antispam_banned": "⛔ Auto-banned — warn limit reached!",

    # ── stickerban ────────────────────────────────────────────────────────────
    "stickerban_toggled": "Sticker ban: {state}\nStickers will be auto-deleted.",

    # ── nightmode ─────────────────────────────────────────────────────────────
    "nightmode_on":  "Night mode ON — chat is locked.",
    "nightmode_off": "Night mode OFF — chat is now open.",

    # ── /setlang ──────────────────────────────────────────────────────────────
    "setlang_choose": "🌍 <b>Choose a language for this group:</b>",
    "setlang_set":    "✅ Language set to <b>{lang_name}</b>.",

    # ── /post pre-flight ──────────────────────────────────────────────────────
    "post_no_groups": (
        "❌ <b>NO GROUPS FOUND</b>\n\n"
        "This bot has not been added to any group yet.\n"
        "Add the bot to a group first, then try /post again."
    ),
    "post_no_access": (
        "❌ <b>NO ACCESSIBLE GROUPS</b>\n\n"
        "You must be an admin or owner in a group this bot manages "
        "to post there."
    ),

    # ── broadcast ─────────────────────────────────────────────────────────────
    "broadcast_queued": (
        "📤 Broadcast queued! Sending to <b>{count}</b> target(s) "
        "in the background."
    ),
    "broadcast_done": (
        "📢 <b>Broadcast complete.</b>\n"
        "Sent: <b>{sent}</b>  Failed: <b>{failed}</b>"
    ),

    # ── fun plugin ────────────────────────────────────────────────────────────
    "dice_result": "🎲 You rolled: <b>{result}</b>",
    "coin_heads":  "🪙 <b>Heads!</b>",
    "coin_tails":  "🪙 <b>Tails!</b>",
    "8ball_q":     "🎱 <b>{question}</b>\n\n<i>{answer}</i>",
}
