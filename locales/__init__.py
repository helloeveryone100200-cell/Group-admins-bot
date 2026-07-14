"""
Locale registry.  Import ALL_STRINGS / LANG_NAMES from here.
"""
from locales.en import STRINGS as _EN
from locales.my import STRINGS as _MY
from locales.zh import STRINGS as _ZH

ALL_STRINGS: dict[str, dict[str, str]] = {
    "en": _EN,
    "my": _MY,
    "zh": _ZH,
}

LANG_NAMES: dict[str, str] = {
    "en": "🇬🇧 English",
    "my": "🇲🇲 မြန်မာ",
    "zh": "🇨🇳 中文",
}
