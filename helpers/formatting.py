"""
Text formatting helpers — Bold, Italic, Mono (HTML parse_mode)
"""

def bold(text: str) -> str:
    """<b>text</b>"""
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    """<i>text</i>"""
    return f"<i>{text}</i>"


def mono(text: str) -> str:
    """<code>text</code>"""
    return f"<code>{text}</code>"


def mention(name: str, user_id: int) -> str:
    """Clickable user mention."""
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def hlink(text: str, url: str) -> str:
    return f'<a href="{url}">{text}</a>'


def header(text: str) -> str:
    return f"<b>━━━ {text} ━━━</b>"


def success(text: str) -> str:
    return f"<b>✅ {text}</b>"


def error(text: str) -> str:
    return f"<b>❌ {text}</b>"


def warn_msg(text: str) -> str:
    return f"<b>⚠️ {text}</b>"


def info_line(label: str, value: str) -> str:
    return f"{bold(label + ':')} {mono(value)}"
