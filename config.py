import os

# ─────────────────────────────────────────────
#  Read all secrets from Render environment
# ─────────────────────────────────────────────

BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
MONGO_URI: str = os.environ.get("MONGO_URI", "")

_raw_owners = os.environ.get("OWNER_IDS", "")
OWNER_IDS: list[int] = [
    int(x.strip()) for x in _raw_owners.split(",") if x.strip().isdigit()
]

PORT: int = int(os.environ.get("PORT", 8080))

# Optional — Redis URL for caching, rate-limiting, and ARQ task queue.
# Leave unset to run without Redis (bot stays fully functional, just slower).
REDIS_URL: str | None = os.environ.get("REDIS_URL") or None

# Validate required vars on startup
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is not set!")
if not OWNER_IDS:
    raise RuntimeError("OWNER_IDS environment variable is not set or invalid!")

# ─── Bot identity ──────────────────────────────
BOT_NAME = "Group Admin Bot"
VERSION  = "3.0.0"
