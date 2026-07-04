"""
Schedule handler — /addschedule, /schedules, /delschedule
Supports two types:
  • one_time  — fires once at a given datetime (YYYY-MM-DD HH:MM), then removed
  • always    — fires every day at a given time (HH:MM)

Delete by ID or name:
  /delschedule 3          ← by numeric ID shown in /schedules
  /delschedule morning    ← by name

Task lifecycle:
  • Both one_time and always tasks are tracked in _task_registry keyed by
    (chat_id, name), so re-saving a schedule always cancels the old task first.
  • one_time tasks re-check the DB before firing to prevent stale sends.
  • All datetimes use server-local time.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application
from telegram.constants import ParseMode

import database as db
from helpers.decorators import admin_only
from helpers.formatting import bold, italic, mono, error, success, header, info_line
from helpers.utils import send_and_delete, parse_time, parse_datetime, seconds_until

log = logging.getLogger(__name__)

# Unified task registry: (chat_id, name) → asyncio.Task
_task_registry: dict[tuple[int, str], asyncio.Task] = {}


# ── internal task runners ─────────────────────────────────────────────────────

async def _fire_message(bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
    except Exception as e:
        log.warning("Schedule fire failed for chat %s: %s", chat_id, e)


async def _run_always(bot, chat_id: int, name: str, hour: int, minute: int, text: str) -> None:
    """Fires daily at HH:MM until cancelled."""
    while True:
        wait = seconds_until(hour, minute)
        await asyncio.sleep(wait)
        sched = await db.get_schedule(chat_id, name)
        if not sched or sched.get("schedule_type") != "always":
            break
        await _fire_message(bot, chat_id, sched.get("message", text))


async def _run_once(bot, chat_id: int, name: str, target: datetime, text: str) -> None:
    """Fires once at target datetime, re-checks DB before sending, then removes itself."""
    wait = (target - datetime.now()).total_seconds()
    if wait > 0:
        await asyncio.sleep(wait)
    # Guard: re-check DB
    sched = await db.get_schedule(chat_id, name)
    if not sched or sched.get("schedule_type") != "one_time":
        log.info("one_time '%s' (chat %s) gone — skipping fire.", name, chat_id)
        return
    await _fire_message(bot, sched["chat_id"], sched.get("message", text))
    await db.delete_schedule(chat_id, name)
    _task_registry.pop((chat_id, name), None)
    log.info("one_time '%s' fired and removed (chat %s).", name, chat_id)


# ── task registry helpers ─────────────────────────────────────────────────────

def _cancel_existing(chat_id: int, name: str) -> None:
    key = (chat_id, name)
    old = _task_registry.pop(key, None)
    if old and not old.done():
        old.cancel()


def _register_always(app: Application, chat_id: int, sched: dict) -> None:
    name = sched["name"]
    _cancel_existing(chat_id, name)
    task = asyncio.create_task(
        _run_always(app.bot, chat_id, name,
                    sched["hour"], sched["minute"], sched["message"])
    )
    _task_registry[(chat_id, name)] = task


def _register_onetime(app: Application, chat_id: int, sched: dict) -> None:
    name = sched["name"]
    target = sched["target_dt"]
    if isinstance(target, str):
        target = datetime.fromisoformat(target)
    if target <= datetime.now():
        return
    _cancel_existing(chat_id, name)
    task = asyncio.create_task(
        _run_once(app.bot, chat_id, name, target, sched["message"])
    )
    _task_registry[(chat_id, name)] = task


# ── /addschedule ──────────────────────────────────────────────────────────────

def _usage_text() -> str:
    return (
        f"{bold('Usage:')}\n"
        f"{mono('/addschedule')} {italic('<name>')} {bold('one_time')} "
        f"{italic('YYYY-MM-DD HH:MM')} {italic('<message>')}\n"
        f"{mono('/addschedule')} {italic('<name>')} {bold('always')} "
        f"{italic('HH:MM')} {italic('<message>')}\n\n"
        f"• {bold('one_time')} — fires once at given date+time, then auto-removed\n"
        f"• {bold('always')} — fires every day at given time"
    )


@admin_only
async def addschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if len(args) < 4:
        await send_and_delete(msg, error("Too few arguments.\n\n" + _usage_text()), parse_mode=ParseMode.HTML)
        return

    name = args[0].lower()
    sched_type = args[1].lower()

    if sched_type not in ("one_time", "always"):
        await send_and_delete(
            msg,
            error(f"Type must be {bold('one_time')} or {bold('always')}."),
            parse_mode=ParseMode.HTML,
        )
        return

    if sched_type == "always":
        parsed = parse_time(args[2])
        if not parsed:
            await send_and_delete(
                msg, error("Invalid time. Use HH:MM (e.g. 09:00)."), parse_mode=ParseMode.HTML
            )
            return
        hour, minute = parsed
        message_text = " ".join(args[3:])
        doc = {"schedule_type": "always", "hour": hour, "minute": minute, "message": message_text}
        sched_id = await db.save_schedule(chat.id, name, doc)
        _register_always(context.application, chat.id, {**doc, "name": name})
        await send_and_delete(
            msg,
            success(
                f"✅ Schedule saved.\n"
                f"{info_line('ID', bold(f'#{sched_id}'))}\n"
                f"{info_line('Name', mono(name))}\n"
                f"{info_line('Type', bold('always'))}\n"
                f"{info_line('Time', mono(f'{hour:02d}:{minute:02d}'))} daily\n"
                f"{info_line('Message', italic(message_text[:80]))}"
            ),
            parse_mode=ParseMode.HTML,
        )

    else:  # one_time
        if len(args) < 5:
            await send_and_delete(msg, error("Too few arguments.\n\n" + _usage_text()), parse_mode=ParseMode.HTML)
            return
        dt_str = f"{args[2]} {args[3]}"
        target = parse_datetime(dt_str)
        if not target:
            await send_and_delete(
                msg,
                error("Invalid datetime. Use YYYY-MM-DD HH:MM (e.g. 2026-07-10 14:30)."),
                parse_mode=ParseMode.HTML,
            )
            return
        if target <= datetime.now():
            await send_and_delete(msg, error("That datetime is in the past."), parse_mode=ParseMode.HTML)
            return
        message_text = " ".join(args[4:])
        doc = {"schedule_type": "one_time", "target_dt": target.isoformat(), "message": message_text}
        sched_id = await db.save_schedule(chat.id, name, doc)
        _register_onetime(context.application, chat.id, {**doc, "name": name})
        await send_and_delete(
            msg,
            success(
                f"✅ Schedule saved.\n"
                f"{info_line('ID', bold(f'#{sched_id}'))}\n"
                f"{info_line('Name', mono(name))}\n"
                f"{info_line('Type', bold('one_time'))}\n"
                f"{info_line('Fires at', mono(target.strftime('%Y-%m-%d %H:%M')))}\n"
                f"{info_line('Message', italic(message_text[:80]))}"
            ),
            parse_mode=ParseMode.HTML,
        )


# ── /schedules ────────────────────────────────────────────────────────────────

@admin_only
async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    scheds = await db.get_all_schedules(chat.id)
    if not scheds:
        await send_and_delete(msg, italic("No schedules set for this chat."), parse_mode=ParseMode.HTML)
        return

    lines = [header("📅 Schedules")]
    for s in scheds:
        stype = s.get("schedule_type", "?")
        sid = s.get("sched_id", "?")
        if stype == "always":
            time_info = f"{s.get('hour', 0):02d}:{s.get('minute', 0):02d} daily"
        else:
            dt = s.get("target_dt", "?")
            if isinstance(dt, str) and "T" in dt:
                dt = dt.replace("T", " ")[:16]
            time_info = str(dt)
        running = "🟢" if _task_registry.get((chat.id, s["name"])) else "⚫"
        lines.append(
            f"\n{running} {bold(f'#{sid}')} · {mono(s['name'])}\n"
            f"  {info_line('Type', bold(stype))}\n"
            f"  {info_line('Time', mono(time_info))}\n"
            f"  {info_line('Msg', italic(str(s.get('message', ''))[:60]))}"
        )
    lines.append(f"\n{italic('Delete: /delschedule <id> or /delschedule <name>')}")
    await send_and_delete(msg, "\n".join(lines), parse_mode=ParseMode.HTML)


# ── /delschedule ──────────────────────────────────────────────────────────────

@admin_only
async def delschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Delete a schedule by numeric ID or name:
      /delschedule 3
      /delschedule morning
    """
    msg = update.effective_message
    chat = update.effective_chat
    args = context.args or []

    if not args:
        await send_and_delete(
            msg,
            error(
                f"Usage:\n"
                f"{mono('/delschedule')} {italic('<id>')}   — delete by ID\n"
                f"{mono('/delschedule')} {italic('<name>')} — delete by name"
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    token = args[0].lstrip("#")  # allow "#3" or "3"

    if token.isdigit():
        # ── delete by ID ──────────────────────────────────────────────────────
        sched_id = int(token)
        deleted_doc = await db.delete_schedule_by_id(chat.id, sched_id)
        if not deleted_doc:
            await send_and_delete(
                msg,
                error(f"No schedule with ID {bold(f'#{sched_id}')} found.\nUse /schedules to see IDs."),
                parse_mode=ParseMode.HTML,
            )
            return
        name = deleted_doc["name"]
        _cancel_existing(chat.id, name)
        await send_and_delete(
            msg,
            success(f"Schedule {bold(f'#{sched_id}')} ({mono(name)}) deleted."),
            parse_mode=ParseMode.HTML,
        )
    else:
        # ── delete by name ────────────────────────────────────────────────────
        name = token.lower()
        _cancel_existing(chat.id, name)
        deleted = await db.delete_schedule(chat.id, name)
        if deleted:
            await send_and_delete(
                msg, success(f"Schedule {mono(name)} deleted."), parse_mode=ParseMode.HTML
            )
        else:
            await send_and_delete(
                msg,
                error(f"No schedule named {mono(name)} found.\nUse /schedules to see all schedules."),
                parse_mode=ParseMode.HTML,
            )


# ── startup restore ───────────────────────────────────────────────────────────

async def restore_schedules(app: Application) -> None:
    """Called on bot startup — restores all active schedules from MongoDB."""
    try:
        all_scheds = await db.get_all_schedules_global()
        restored = 0
        for s in all_scheds:
            chat_id = s["chat_id"]
            stype = s.get("schedule_type")
            if stype == "always":
                _register_always(app, chat_id, s)
                restored += 1
            elif stype == "one_time":
                target = s.get("target_dt")
                if isinstance(target, str):
                    target = datetime.fromisoformat(target)
                if target and target > datetime.now():
                    _register_onetime(app, chat_id, s)
                    restored += 1
                else:
                    await db.delete_schedule(chat_id, s["name"])
        log.info("Restored %d active schedule(s) from DB.", restored)
    except Exception as e:
        log.warning("Could not restore schedules: %s", e)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("addschedule", addschedule))
    app.add_handler(CommandHandler("schedules", list_schedules))
    app.add_handler(CommandHandler("delschedule", delschedule))
