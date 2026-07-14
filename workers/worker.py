"""
ARQ worker entry point.

Start with:
    arq workers.worker.WorkerSettings

Requires environment variables: REDIS_URL, BOT_TOKEN, MONGO_URI, OWNER_IDS.
The worker process connects to the same MongoDB as the bot but runs
independently — it does NOT share the bot's asyncio event loop.
"""
from __future__ import annotations
import logging
import os

from arq.connections import RedisSettings
from telegram import Bot

from config import BOT_TOKEN, REDIS_URL
from workers.tasks import broadcast_all, broadcast_group, broadcast_user

log = logging.getLogger(__name__)

_REDIS_DSN = REDIS_URL or "redis://localhost:6379"


async def startup(ctx: dict) -> None:
    ctx["bot"] = Bot(token=BOT_TOKEN)
    log.info("ARQ worker started — Telegram bot client ready.")


async def shutdown(ctx: dict) -> None:
    try:
        await ctx["bot"].close()
    except Exception:
        pass
    log.info("ARQ worker shut down cleanly.")


class WorkerSettings:
    functions   = [broadcast_all, broadcast_group, broadcast_user]
    on_startup  = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(_REDIS_DSN)
    max_jobs    = 10
    job_timeout = 300   # 5-minute timeout per job
    keep_result = 3600  # keep job result for 1 hour
