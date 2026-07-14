"""
Lightweight i18n (internationalisation) helper.

Usage:
    from helpers.i18n import t
    text = t(lang, "captcha_toggled", state="ENABLED ✅")

• `lang` is the two-letter code stored per-group in MongoDB ("en"/"my"/"zh").
• Falls back to English automatically when a key is missing in the requested
  language, so adding new strings to en.py works immediately everywhere.
• `LANG_NAMES` is re-exported here for /setlang UI convenience.
"""
from __future__ import annotations
from locales import ALL_STRINGS, LANG_NAMES   # noqa: F401 (re-exported)


def t(lang: str, key: str, **kwargs: object) -> str:
    """Translate `key` into `lang`, substituting any `kwargs` placeholders."""
    strings = ALL_STRINGS.get(lang) or ALL_STRINGS["en"]
    template = strings.get(key) or ALL_STRINGS["en"].get(key, key)
    return template.format(**kwargs) if kwargs else template
