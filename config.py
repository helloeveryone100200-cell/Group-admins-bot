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

# Validate required vars on startup
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is not set!")
if not OWNER_IDS:
    raise RuntimeError("OWNER_IDS environment variable is not set or invalid!")

# ─── Bot identity ──────────────────────────────
BOT_NAME = "Group Admin Bot"
VERSION  = "2.0.0"
