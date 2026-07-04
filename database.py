"""
MongoDB async operations via Motor.
All collections are lazily initialised on first use.
"""
from __future__ import annotations

import motor.motor_asyncio
from config import MONGO_URI

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        _db = _client["admin_bot"]
    return _db


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
    return len(warns)


async def get_warns(chat_id: int, user_id: int) -> list[str]:
    db = get_db()
    doc = await db.warnings.find_one({"chat_id": chat_id, "user_id": user_id})
    return doc["warns"] if doc else []


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
    return len(warns)


async def reset_warns(chat_id: int, user_id: int) -> None:
    db = get_db()
    await db.warnings.delete_one({"chat_id": chat_id, "user_id": user_id})


async def get_warn_limit(chat_id: int) -> int:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get("warn_limit", 3) if doc else 3


async def set_warn_limit(chat_id: int, limit: int) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"warn_limit": limit}}, upsert=True
    )


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


async def remove_blacklist(chat_id: int, word: str) -> bool:
    db = get_db()
    doc = await db.blacklist.find_one({"chat_id": chat_id})
    if not doc or word.lower() not in doc.get("words", []):
        return False
    await db.blacklist.update_one(
        {"chat_id": chat_id}, {"$pull": {"words": word.lower()}}
    )
    return True


async def get_blacklist(chat_id: int) -> list[str]:
    db = get_db()
    doc = await db.blacklist.find_one({"chat_id": chat_id})
    return doc.get("words", []) if doc else []


async def get_blacklist_mode(chat_id: int) -> str:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get("blacklist_mode", "delete") if doc else "delete"


async def set_blacklist_mode(chat_id: int, mode: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"blacklist_mode": mode}}, upsert=True
    )


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

_flood_tracker: dict[tuple[int, int], list] = {}


async def set_flood_limit(chat_id: int, limit: int) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"flood_limit": limit}}, upsert=True
    )


async def get_flood_limit(chat_id: int) -> int:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get("flood_limit", 0) if doc else 0


async def set_flood_mode(chat_id: int, mode: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"flood_mode": mode}}, upsert=True
    )


async def get_flood_mode(chat_id: int) -> str:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get("flood_mode", "mute") if doc else "mute"


# ── Locks ─────────────────────────────────────────────────────────────────────

async def set_lock(chat_id: int, lock_type: str, value: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id},
        {"$set": {f"lock_{lock_type}": value}},
        upsert=True,
    )


async def get_lock(chat_id: int, lock_type: str) -> bool:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get(f"lock_{lock_type}", False) if doc else False


# ── Stats ─────────────────────────────────────────────────────────────────────

async def count_chats() -> int:
    db = get_db()
    return await db.settings.count_documents({})


async def register_chat(chat_id: int, title: str) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"title": title}}, upsert=True
    )


# ── Captcha ───────────────────────────────────────────────────────────────────

async def set_captcha(chat_id: int, enabled: bool) -> None:
    db = get_db()
    await db.settings.update_one(
        {"chat_id": chat_id}, {"$set": {"captcha": enabled}}, upsert=True
    )


async def get_captcha(chat_id: int) -> bool:
    db = get_db()
    doc = await db.settings.find_one({"chat_id": chat_id})
    return doc.get("captcha", False) if doc else False


_pending_captcha: dict[tuple[int, int], int] = {}  # (chat_id, user_id) -> msg_id


# ── Schedules ─────────────────────────────────────────────────────────────────

async def save_schedule(chat_id: int, name: str, doc: dict) -> None:
    """
    Save or update a schedule for a chat.
    doc must include at minimum: schedule_type, message
    For 'always': hour, minute
    For 'one_time': target_dt (ISO string)
    """
    db = get_db()
    payload = {"chat_id": chat_id, "name": name, **doc}
    await db.schedules.update_one(
        {"chat_id": chat_id, "name": name},
        {"$set": payload},
        upsert=True,
    )


async def get_schedule(chat_id: int, name: str) -> dict | None:
    db = get_db()
    return await db.schedules.find_one({"chat_id": chat_id, "name": name})


async def get_all_schedules(chat_id: int) -> list[dict]:
    """Return all schedules for one chat."""
    db = get_db()
    cursor = db.schedules.find({"chat_id": chat_id})
    return [doc async for doc in cursor]


async def get_all_schedules_global() -> list[dict]:
    """Return every schedule across all chats (used on startup restore)."""
    db = get_db()
    cursor = db.schedules.find({})
    return [doc async for doc in cursor]


async def delete_schedule(chat_id: int, name: str) -> bool:
    db = get_db()
    result = await db.schedules.delete_one({"chat_id": chat_id, "name": name})
    return result.deleted_count > 0
