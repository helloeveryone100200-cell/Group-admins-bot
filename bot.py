"""
Main entry point — Group Admin Bot
Reads BOT_TOKEN, MONGO_URI, OWNER_IDS from Render environment.
Python 3.10+ / 3.14 compatible async event loop setup.
"""
import asyncio
import logging
import signal

from telegram import Update
from telegram.ext import Application, TypeHandler, ApplicationHandlerStop

from config import BOT_TOKEN, BOT_NAME, VERSION, OWNER_IDS
from keep_alive import keep_alive
import database as db

import importlib
from pathlib import Path

import handlers.admin      as h_admin
import handlers.promote    as h_promote
import handlers.pins       as h_pins
import handlers.purge      as h_purge
import handlers.locks      as h_locks
import handlers.welcome    as h_welcome
import handlers.rules      as h_rules
import handlers.notes      as h_notes
import handlers.filters_bl as h_filters
import handlers.antiflood  as h_antiflood
import handlers.info       as h_info
import handlers.misc       as h_misc
import handlers.schedule   as h_schedule
import handlers.owner      as h_owner

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    log.error("Exception while handling update:", exc_info=context.error)


async def _update_middleware(update: Update, context) -> None:
    """
    Group=-1 middleware — executes before every other handler.

    • Registers users and groups in MongoDB on first contact.
    • Silently drops updates from globally blocked users/groups.
    """
    user = update.effective_user
    chat = update.effective_chat

    if user and not user.is_bot:
        # Track this user so /listusers and /broadcast user work
        await db.register_user(user.id, user.username, user.full_name or "")
        # Owners are never blocked
        if user.id not in OWNER_IDS and await db.is_user_blocked(user.id):
            raise ApplicationHandlerStop()

    if chat and chat.type in ("group", "supergroup"):
        # Track this group so /listgroups and /broadcast all work
        await db.register_chat(chat.id, chat.title or "Unknown")
        # Auto-leave blocked groups
        if await db.is_group_blocked(chat.id):
            try:
                await context.bot.leave_chat(chat.id)
            except Exception:
                pass
            raise ApplicationHandlerStop()


def _load_plugins(app: Application) -> None:
    """Auto-load every plugin/*.py that exposes a register(app) function."""
    plugin_dir = Path(__file__).parent / "plugins"
    if not plugin_dir.exists():
        return
    for f in sorted(plugin_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"plugins.{f.stem}")
            if hasattr(mod, "register"):
                mod.register(app)
                log.info("✅ Plugin loaded: %s", f.stem)
        except Exception as exc:
            log.warning("❌ Plugin %s failed to load: %s", f.stem, exc)


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    # Group=-1: runs first, registers users/groups, enforces global blocks
    app.add_handler(TypeHandler(Update, _update_middleware), group=-1)
    h_misc.register(app)
    h_owner.register(app)       # owner panel commands (incl. /broadcast)
    h_admin.register(app)
    h_promote.register(app)
    h_pins.register(app)
    h_purge.register(app)
    h_locks.register(app)
    h_welcome.register(app)
    h_rules.register(app)
    h_notes.register(app)
    h_filters.register(app)
    h_antiflood.register(app)
    h_info.register(app)
    h_schedule.register(app)
    _load_plugins(app)          # drop-in plugins from plugins/
    app.add_error_handler(error_handler)
    return app


async def run_bot() -> None:
    """
    Fully async runner — compatible with Python 3.10 / 3.12 / 3.14.
    Uses explicit async context manager to avoid event-loop-in-thread
    RuntimeError on newer Python versions.
    """
    app = build_app()
    log.info(f"Starting {BOT_NAME} v{VERSION} …")

    async with app:
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        log.info("Bot is polling …")

        # Restore persisted schedules from MongoDB
        await h_schedule.restore_schedules(app)

        stop_event = asyncio.Event()

        def _handle_signal(*_):
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except (NotImplementedError, RuntimeError):
                pass  # Windows / restricted environments

        await stop_event.wait()
        log.info("Shutdown — stopping bot …")
        await app.updater.stop()
        await app.stop()


def main() -> None:
    keep_alive()
    log.info("Keep-alive web server started.")
    # asyncio.run() creates a fresh event loop — safe on Python 3.10/3.12/3.14
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
