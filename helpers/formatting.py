"""
Text formatting helpers — Unicode Bold Sans-Serif font style + HTML parse_mode.

All display text uses Unicode Mathematical Bold Sans-Serif characters
(𝗟𝗜𝗞𝗘 𝗧𝗛𝗜𝗦) so every message renders in a bold, military-style font
on all Telegram clients without needing a special font.

HTML tags (<a href=...>, <i>, <code>) are kept as-is since they must
pass through Telegram's HTML parser.
"""

# ── Unicode Bold Sans-Serif character maps ─────────────────────────────────────

_U = {
    'A':'𝗔','B':'𝗕','C':'𝗖','D':'𝗗','E':'𝗘','F':'𝗙','G':'𝗚','H':'𝗛',
    'I':'𝗜','J':'𝗝','K':'𝗞','L':'𝗟','M':'𝗠','N':'𝗡','O':'𝗢','P':'𝗣',
    'Q':'𝗤','R':'𝗥','S':'𝗦','T':'𝗧','U':'𝗨','V':'𝗩','W':'𝗪','X':'𝗫',
    'Y':'𝗬','Z':'𝗭',
    'a':'𝗮','b':'𝗯','c':'𝗰','d':'𝗱','e':'𝗲','f':'𝗳','g':'𝗴','h':'𝗵',
    'i':'𝗶','j':'𝗷','k':'𝗸','l':'𝗹','m':'𝗺','n':'𝗻','o':'𝗼','p':'𝗽',
    'q':'𝗾','r':'𝗿','s':'𝘀','t':'𝘁','u':'𝘂','v':'𝘃','w':'𝘄','x':'𝘅',
    'y':'𝘆','z':'𝘇',
    '0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰',
    '5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',
}


def _bs(text: str) -> str:
    """Convert ASCII letters/digits to Unicode Bold Sans-Serif glyphs."""
    return "".join(_U.get(ch, ch) for ch in text)


# ── Public helpers ─────────────────────────────────────────────────────────────

def bold(text: str) -> str:
    """Render text in Unicode Bold Sans-Serif (no HTML tag needed)."""
    return _bs(str(text))


def italic(text: str) -> str:
    """<i>text</i> — keep HTML italic for contrast."""
    return f"<i>{text}</i>"


def mono(text: str) -> str:
    """<code>text</code> — monospace for IDs, values, commands."""
    return f"<code>{text}</code>"


def mention(name: str, user_id: int) -> str:
    """Clickable user mention (HTML link, name rendered in bold sans)."""
    return f'<a href="tg://user?id={user_id}">{_bs(name)}</a>'


def hlink(text: str, url: str) -> str:
    return f'<a href="{url}">{_bs(text)}</a>'


def header(text: str) -> str:
    """Section header — ALL CAPS bold sans with decorative rule."""
    return f"{_bs('━━━ ' + text.upper() + ' ━━━')}"


def success(text: str) -> str:
    return f"✅ {_bs(text)}"


def error(text: str) -> str:
    return f"❌ {_bs(text)}"


def warn_msg(text: str) -> str:
    return f"⚠️ {_bs(text)}"


def info_line(label: str, value: str) -> str:
    """𝗟𝗔𝗕𝗘𝗟: <code>value</code>"""
    return f"{_bs(label.upper() + ':')} {mono(value)}"
