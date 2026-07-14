"""
MongoDB async operations via Motor, with Redis caching (cache.py).

Read-path:  check Redis first → on miss, query MongoDB and populate cache.
Write-path: update MongoDB → invalidate the relevant cache key(s).
Fallback:   if Redis is unavailable, every function works directly via MongoDB.
"""
from __future__ import annotations

import motor.motor_asyncio
from config import MONGO_URI
from cache import cget, cset, cdel, SETTINGS_TTL, WARN_TTL, LIST_TTL, BLOCK_TTL

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        _db = _client["admin_bot"]
    return _db


# ── Settings cache helpers ─────────────────────────────────────────────────────
# One Redis key per group holds the full settings document.
# All settings reads go through _get_settings(); every settings write calls
# _invalidate_settings() so the cache is always consistent.

async def _get_settings(chat_id: int) -> dict:
    key = f"settings:{chat_id}"
    cached = await cget(key)
    if cached is not None:
        return cached
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    result: dict = dict(doc) if doc else {}
    result.pop("_id", None)   # ObjectId is not JSON-serialisable
    await cset(key, result, SETTINGS_TTL)
    return result


async def _invalidate_settings(chat_id: int) -> None:
    await cdel(f"settings:{chat_id}")


# ── Warnings ──────────────────────────────────────────────────────────────────

async def add_warn(chat_id: int, user_id: int, reason: str) -> int:
    db = get_db()
    doc = await db.warnings.find_one({"chat_id": chat_id, "user_id": user_id})
    warns = doc["warns"] if doc else []
    warns.append(reason)
    await db.warnings.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"warns": warns}},
        upsert=True,
    )
    await cdel(f"warns:{chat_id}:{user_id}")
    return len(warns)


async def get_warns(chat_id: int, user_id: int) -> list[str]:
    key = f"warns:{chat_id}:{user_id}"
    cached = await cget(key)
    if cached is not None:
        return cached
    db = get_db()
    doc = await db.warnings.find_one({"chat_id": chat_id, "user_id": user_id})
    result = doc["warns"] if doc else []
    await cset(key, result, WARN_TTL)
    return result


async def remove_warn(chat_id: int, user_id: int) -> int:
    db = get_db()
    doc = await db.warnings.find_one({"chat_id": chat_id, "user_id": user_id})
    if not doc or not doc["warns"]:
        return 0
    warns = doc["warns"][:-1]
    await db.warnings.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"warns": warns}},
    )
    await cdel(f"warns:{chat_id}:{user_id}")
    return len(warns)


async def reset_warns(chat_id: int, user_id: int) -> None:
    db = get_db()
    await db.warnings.delete_one({"chat_id": chat_id, "user_id": user_id})
    await cdel(f"warns:{chat_id}:{user_id}")


async def get_warn_limit(chat_id: int) -> int:
    doc = await _get_settings(chat_id)
    return doc.get("warn_limit", 3)


async def set_warn_limit(chat_id: int, limit: int) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"warn_limit": limit}}, upsert=True
    )
    await _invalidate_settings(chat_id)


# ── Welcome / Goodbye ─────────────────────────────────────────────────────────

async def set_welcome(chat_id: int, text: str) -> None:
    db = get_db()
    await db.welcome.update_one(
        {"chat_id": chat_id}, {"$set": {"welcome": text}}, upsert=True
    )


async def get_welcome(chat_id: int) -> str | None:
    db = get_db()
    doc = await db.welcome.find_one({"chat_id": chat_id})
    return doc.get("welcome") if doc else None


async def clear_welcome(chat_id: int) -> None:
    db = get_db()
    await db.welcome.update_one({"chat_id": chat_id}, {"$unset": {"welcome": ""}})


async def set_goodbye(chat_id: int, text: str) -> None:
    db = get_db()
    await db.welcome.update_one(
        {"chat_id": chat_id}, {"$set": {"goodbye": text}}, upsert=True
    )


async def get_goodbye(chat_id: int) -> str | None:
    db = get_db()
    doc = await db.welcome.find_one({"chat_id": chat_id})
    return doc.get("goodbye") if doc else None


async def clear_goodbye(chat_id: int) -> None:
    db = get_db()
    await db.welcome.update_one({"chat_id": chat_id}, {"$unset": {"goodbye": ""}})


# ── Rules ─────────────────────────────────────────────────────────────────────

async def set_rules(chat_id: int, text: str) -> None:
    db = get_db()
    await db.rules.update_one(
        {"chat_id": chat_id}, {"$set": {"text": text}}, upsert=True
    )


async def get_rules(chat_id: int) -> str | None:
    db = get_db()
    doc = await db.rules.find_one({"chat_id": chat_id})
    return doc.get("text") if doc else None


async def clear_rules(chat_id: int) -> None:
    db = get_db()
    await db.rules.delete_one({"chat_id": chat_id})


# ── Notes ─────────────────────────────────────────────────────────────────────

async def save_note(chat_id: int, name: str, text: str) -> None:
    db = get_db()
    await db.notes.update_one(
        {"chat_id": chat_id, "name": name.lower()},
        {"$set": {"text": text}},
        upsert=True,
    )


async def get_note(chat_id: int, name: str) -> str | None:
    db = get_db()
    doc = await db.notes.find_one({"chat_id": chat_id, "name": name.lower()})
    return doc.get("text") if doc else None


async def get_all_notes(chat_id: int) -> list[str]:
    db = get_db()
    cursor = db.notes.find({"chat_id": chat_id}, {"name": 1})
    return [doc["name"] async for doc in cursor]


async def delete_note(chat_id: int, name: str) -> bool:
    db = get_db()
    result = await db.notes.delete_one({"chat_id": chat_id, "name": name.lower()})
    return result.deleted_count > 0


async def delete_all_notes(chat_id: int) -> None:
    db = get_db()
    await db.notes.delete_many({"chat_id": chat_id})


# ── Blacklist ─────────────────────────────────────────────────────────────────

async def add_blacklist(chat_id: int, word: str) -> None:
    db = get_db()
    await db.blacklist.update_one(
        {"chat_id": chat_id},
        {"$addToSet": {"words": word.lower()}},
        upsert=True,
    )
    await cdel(f"blacklist:{chat_id}")


async def remove_blacklist(chat_id: int, word: str) -> bool:
    db = get_db()
    doc = await db.blacklist.find_one({"chat_id": chat_id})
    if not doc or word.lower() not in doc.get("words", []):
        return False
    await db.blacklist.update_one(
        {"chat_id": chat_id}, {"$pull": {"words": word.lower()}}
    )
    await cdel(f"blacklist:{chat_id}")
    return True


async def get_blacklist(chat_id: int) -> list[str]:
    key = f"blacklist:{chat_id}"
    cached = await cget(key)
    if cached is not None:
        return cached
    db = get_db()
    doc = await db.blacklist.find_one({"chat_id": chat_id})
    result = doc.get("words", []) if doc else []
    await cset(key, result, LIST_TTL)
    return result


async def get_blacklist_mode(chat_id: int) -> str:
    doc = await _get_settings(chat_id)
    return doc.get("blacklist_mode", "delete")


async def set_blacklist_mode(chat_id: int, mode: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"blacklist_mode": mode}}, upsert=True
    )
    await _invalidate_settings(chat_id)


# ── Filters ───────────────────────────────────────────────────────────────────

async def add_filter(chat_id: int, keyword: str, reply: str) -> None:
    db = get_db()
    await db.filters.update_one(
        {"chat_id": chat_id, "keyword": keyword.lower()},
        {"$set": {"reply": reply}},
        upsert=True,
    )


async def get_filter(chat_id: int, keyword: str) -> str | None:
    db = get_db()
    doc = await db.filters.find_one(
        {"chat_id": chat_id, "keyword": keyword.lower()}
    )
    return doc.get("reply") if doc else None


async def get_all_filters(chat_id: int) -> list[str]:
    db = get_db()
    cursor = db.filters.find({"chat_id": chat_id}, {"keyword": 1})
    return [doc["keyword"] async for doc in cursor]


async def delete_filter(chat_id: int, keyword: str) -> bool:
    db = get_db()
    result = await db.filters.delete_one(
        {"chat_id": chat_id, "keyword": keyword.lower()}
    )
    return result.deleted_count > 0


async def delete_all_filters(chat_id: int) -> None:
    db = get_db()
    await db.filters.delete_many({"chat_id": chat_id})


# ── Anti-flood ────────────────────────────────────────────────────────────────
# Flood tracking itself is handled in helpers/ratelimit.py via Redis sorted sets.
# The DB functions here persist the limit/mode settings only.

async def set_flood_limit(chat_id: int, limit: int) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"flood_limit": limit}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_flood_limit(chat_id: int) -> int:
    doc = await _get_settings(chat_id)
    return doc.get("flood_limit", 0)


async def set_flood_mode(chat_id: int, mode: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"flood_mode": mode}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_flood_mode(chat_id: int) -> str:
    doc = await _get_settings(chat_id)
    return doc.get("flood_mode", "mute")


# ── Locks ─────────────────────────────────────────────────────────────────────

async def set_lock(chat_id: int, lock_type: str, value: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id},
        {"$set": {f"lock_{lock_type}": value}},
        upsert=True,
    )
    await _invalidate_settings(chat_id)


async def get_lock(chat_id: int, lock_type: str) -> bool:
    doc = await _get_settings(chat_id)
    return doc.get(f"lock_{lock_type}", False)


# ── Stats ─────────────────────────────────────────────────────────────────────

async def count_chats() -> int:
    db = get_db()
    return await db.settings.count_documents({})


async def register_chat(chat_id: int, title: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"title": title}}, upsert=True
    )
    # Title changes are low-priority; let the cache expire naturally.


# ── Antispam / Stickerban / Nightmode ─────────────────────────────────────────

async def set_antispam(chat_id: int, enabled: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"antispam": enabled}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_antispam(chat_id: int) -> bool:
    doc = await _get_settings(chat_id)
    return doc.get("antispam", False)


async def set_stickerban(chat_id: int, enabled: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"stickerban": enabled}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_stickerban(chat_id: int) -> bool:
    doc = await _get_settings(chat_id)
    return doc.get("stickerban", False)


async def set_nightmode(chat_id: int, enabled: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"nightmode": enabled}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_nightmode(chat_id: int) -> bool:
    doc = await _get_settings(chat_id)
    return doc.get("nightmode", False)


# ── Captcha ───────────────────────────────────────────────────────────────────

async def set_captcha(chat_id: int, enabled: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"captcha": enabled}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_captcha(chat_id: int) -> bool:
    doc = await _get_settings(chat_id)
    return doc.get("captcha", False)


_pending_captcha: dict[tuple[int, int], int] = {}  # (chat_id, user_id) -> msg_id


# ── Language (i18n) ───────────────────────────────────────────────────────────

async def set_lang(chat_id: int, lang: str) -> None:
    """Persist the UI language for a group ('en' / 'my' / 'zh')."""
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True
    )
    await _invalidate_settings(chat_id)


async def get_lang(chat_id: int) -> str:
    """Return the UI language code for a group. Defaults to 'en'."""
    doc = await _get_settings(chat_id)
    return doc.get("lang", "en")


# ── Schedules ─────────────────────────────────────────────────────────────────

async def _next_sched_id(chat_id: int) -> int:
    db = get_db()
    result = await db.sched_counters.find_one_and_update(
        {"chat_id": chat_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return result["seq"]


async def save_schedule(chat_id: int, name: str, doc: dict) -> int:
    db = get_db()
    existing = await db.schedules.find_one({"chat_id": chat_id, "name": name})
    if existing:
        sched_id = existing["sched_id"]
    else:
        sched_id = await _next_sched_id(chat_id)
    payload = {"chat_id": chat_id, "name": name, "sched_id": sched_id, **doc}
    await db.schedules.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": payload},
        upsert=True,
    )
    return sched_id


async def get_schedule(chat_id: int, name: str) -> dict | None:
    db = get_db()
    return await db.schedules.find_one({"chat_id": chat_id, "name": name})


async def get_schedule_by_id(chat_id: int, sched_id: int) -> dict | None:
    db = get_db()
    return await db.schedules.find_one({"chat_id": chat_id, "sched_id": sched_id})


async def get_all_schedules(chat_id: int) -> list[dict]:
    db = get_db()
    cursor = db.schedules.find({"chat_id": chat_id}).sort("sched_id", 1)
    return [doc async for doc in cursor]


async def get_all_schedules_global() -> list[dict]:
    db = get_db()
    cursor = db.schedules.find({})
    return [doc async for doc in cursor]


async def delete_schedule(chat_id: int, name: str) -> bool:
    db = get_db()
    result = await db.schedules.delete_one({"chat_id": chat_id, "name": name})
    return result.deleted_count > 0


async def delete_schedule_by_id(chat_id: int, sched_id: int) -> dict | None:
    db = get_db()
    doc = await db.schedules.find_one_and_delete(
        {"chat_id": chat_id, "sched_id": sched_id}
    )
    return doc


# ── User tracking ─────────────────────────────────────────────────────────────

async def register_user(user_id: int, username: str | None, full_name: str) -> None:
    db = get_db()
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "username": username, "full_name": full_name}},
        upsert=True,
    )


async def count_users() -> int:
    db = get_db()
    return await db.users.count_documents({})


async def get_all_groups() -> list[dict]:
    """All groups the bot has ever seen (stored via register_chat)."""
    db = get_db()
    cursor = db.settings.find({}, {"chat_id": 1, "title": 1, "_id": 0})
    return [doc async for doc in cursor]


# ── Global user block ─────────────────────────────────────────────────────────

async def block_user(user_id: int) -> None:
    db = get_db()
    await db.blocked_users.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True,
    )
    await cdel(f"blocked:u:{user_id}")


async def unblock_user(user_id: int) -> bool:
    db = get_db()
    result = await db.blocked_users.delete_one({"user_id": user_id})
    await cdel(f"blocked:u:{user_id}")
    return result.deleted_count > 0


async def is_user_blocked(user_id: int) -> bool:
    key = f"blocked:u:{user_id}"
    cached = await cget(key)
    if cached is not None:
        return cached
    db = get_db()
    result = bool(await db.blocked_users.find_one({"user_id": user_id}))
    await cset(key, result, BLOCK_TTL)
    return result


async def count_blocked_users() -> int:
    db = get_db()
    return await db.blocked_users.count_documents({})


# ── Global group block ────────────────────────────────────────────────────────

async def block_group(chat_id: int, title: str = "") -> None:
    db = get_db()
    await db.blocked_groups.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id, "title": title or str(chat_id)}},
        upsert=True,
    )
    await cdel(f"blocked:g:{chat_id}")


async def unblock_group(chat_id: int) -> bool:
    db = get_db()
    result = await db.blocked_groups.delete_one({"chat_id": chat_id})
    await cdel(f"blocked:g:{chat_id}")
    return result.deleted_count > 0


async def is_group_blocked(chat_id: int) -> bool:
    key = f"blocked:g:{chat_id}"
    cached = await cget(key)
    if cached is not None:
        return cached
    db = get_db()
    result = bool(await db.blocked_groups.find_one({"chat_id": chat_id}))
    await cset(key, result, BLOCK_TTL)
    return result


async def count_blocked_groups() -> int:
    db = get_db()
    return await db.blocked_groups.count_documents({})
