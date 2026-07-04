"""
Main entry point — Group Admin Bot
Reads BOT_TOKEN, MONGO_URI, OWNER_IDS from Render environment.
Python 3.10+ / 3.14 compatible async event loop setup.
"""
import asyncio
import logging
import signal

from telegram import Update
from telegram.ext import Application

from config import BOT_TOKEN, BOT_NAME, VERSION
from keep_alive import keep_alive

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

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    log.error("Exception while handling update:", exc_info=context.error)


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    h_misc.register(app)
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
