"""Telegram workflows and scheduled notifications for birthdays."""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ContextTypes

from . import storage
from .models import Birthday

LOGGER = logging.getLogger(__name__)

BIRTHDAYS_BUTTON = "🎂 Birthdays"
BIRTHDAY_STATE = "birthday_state"
STATE_ADD = "birthday_add"
MAX_NAME_LENGTH = 100


def _menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add birthday", callback_data="birthday:add")],
            [InlineKeyboardButton("📋 List birthdays", callback_data="birthday:list")],
            [InlineKeyboardButton("🗑 Delete birthday", callback_data="birthday:delete")],
        ]
    )


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖ Cancel", callback_data="birthday:menu")]]
    )


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(BIRTHDAY_STATE, None)


def _format_birthday(birthday: Birthday) -> str:
    year = f" ({birthday.birth_year})" if birthday.birth_year else ""
    return f"{birthday.person_name} — {birthday.day:02d}.{birthday.month:02d}{year}"


def _parse_birthday(text: str) -> tuple[str, int, int, int | None]:
    """Parse `name | DD.MM`, `name | DD.MM.YYYY`, or `name | YYYY-MM-DD`."""
    parts = [part.strip() for part in text.split("|", maxsplit=1)]
    if len(parts) != 2:
        raise ValueError("Use: Name | DD.MM (optionally with a birth year)")

    person_name, date_text = parts
    if not person_name or len(person_name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name must be 1–{MAX_NAME_LENGTH} characters")

    parsed: date
    birth_year: int | None = None
    try:
        if len(date_text) == 5:
            day_text, month_text = date_text.split(".")
            parsed = date(2000, int(month_text), int(day_text))
        elif len(date_text) == 10 and date_text[2] == ".":
            day_text, month_text, year_text = date_text.split(".")
            parsed = date(int(year_text), int(month_text), int(day_text))
            birth_year = parsed.year
        else:
            parsed = date.fromisoformat(date_text)
            birth_year = parsed.year
    except ValueError as error:
        raise ValueError(
            "Date must use DD.MM, DD.MM.YYYY, or YYYY-MM-DD format"
        ) from error

    current_year = datetime.now().astimezone().date().year
    if birth_year is not None and not 1900 <= birth_year <= current_year:
        raise ValueError("Birth year must be between 1900 and the current year")
    return person_name, parsed.month, parsed.day, birth_year


async def birthday_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the birthdays menu."""
    clear_state(context)
    user = update.effective_user
    if not user or not update.message:
        return
    await storage.register_user(user.id)
    await update.message.reply_text(
        "🎂 Birthdays\n\nWhat would you like to do?", reply_markup=_menu_markup()
    )


async def birthday_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline buttons belonging to the birthdays menu."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    await query.answer()
    await storage.register_user(user.id)
    data = query.data or ""

    if data == "birthday:menu":
        clear_state(context)
        await query.edit_message_text(
            "🎂 Birthdays\n\nWhat would you like to do?", reply_markup=_menu_markup()
        )
        return

    if data == "birthday:add":
        context.user_data[BIRTHDAY_STATE] = STATE_ADD
        await query.edit_message_text(
            "Send a birthday in this format:\n"
            "Name | DD.MM\n\n"
            "Optional birth year:\n"
            "Name | DD.MM.YYYY\n"
            "or Name | YYYY-MM-DD",
            reply_markup=_cancel_markup(),
        )
        return

    if data == "birthday:list":
        clear_state(context)
        birthdays = await storage.list_birthdays(user.id)
        await _show_list(query, birthdays, "📋 Your birthdays")
        return

    if data == "birthday:delete":
        clear_state(context)
        birthdays = await storage.list_birthdays(user.id)
        if not birthdays:
            await query.edit_message_text(
                "There are no birthdays to delete.", reply_markup=_menu_markup()
            )
            return
        buttons = [
            [
                InlineKeyboardButton(
                    _format_birthday(birthday),
                    callback_data=f"birthday:delete:{birthday.id}",
                )
            ]
            for birthday in birthdays
        ]
        buttons.append(
            [InlineKeyboardButton("⬅ Back", callback_data="birthday:menu")]
        )
        await query.edit_message_text(
            "🗑 Choose a birthday to delete:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "delete":
        try:
            birthday_id = int(parts[2])
        except ValueError:
            return
        birthday = await storage.get_birthday(user.id, birthday_id)
        if birthday is None:
            await query.edit_message_text(
                "That birthday no longer exists.", reply_markup=_menu_markup()
            )
            return
        await query.edit_message_text(
            f"Delete “{_format_birthday(birthday)}”?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Delete",
                            callback_data=f"birthday:delete:confirm:{birthday.id}",
                        ),
                        InlineKeyboardButton(
                            "Cancel", callback_data="birthday:delete"
                        ),
                    ]
                ]
            ),
        )
        return

    if len(parts) == 4 and parts[1:3] == ["delete", "confirm"]:
        try:
            birthday_id = int(parts[3])
        except ValueError:
            return
        deleted = await storage.delete_birthday(user.id, birthday_id)
        await query.edit_message_text(
            "✅ Birthday deleted." if deleted else "That birthday no longer exists.",
            reply_markup=_menu_markup(),
        )


async def _show_list(query, birthdays: list[Birthday], heading: str) -> None:
    if not birthdays:
        text = heading + "\n\nThere are no birthdays saved yet."
    else:
        text = heading + "\n\n" + "\n".join(
            f"• {_format_birthday(birthday)}" for birthday in birthdays
        )
    await query.edit_message_text(text, reply_markup=_menu_markup())


async def handle_birthday_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Consume text input when the user is adding a birthday."""
    if not update.message or not update.effective_user:
        return False
    if context.user_data.get(BIRTHDAY_STATE) != STATE_ADD:
        return False

    try:
        person_name, month, day, birth_year = _parse_birthday(update.message.text.strip())
    except ValueError as error:
        await update.message.reply_text(
            f"I could not save that birthday: {error}.\n\n"
            "Example: Alex | 24.08",
            reply_markup=_cancel_markup(),
        )
        return True

    birthday, created = await storage.add_birthday(
        update.effective_user.id, person_name, month, day, birth_year
    )
    clear_state(context)
    if created:
        message = f"✅ Birthday saved: {_format_birthday(birthday)}"
    else:
        message = f"That birthday is already saved: {_format_birthday(birthday)}"
    await update.message.reply_text(message, reply_markup=_menu_markup())
    return True


def _configured_time(variable: str, default: str, timezone: ZoneInfo) -> time:
    value = os.getenv(variable, default).strip()
    try:
        parsed = time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{variable} must use HH:MM format") from error
    return parsed.replace(tzinfo=timezone)


def _configured_timezone() -> ZoneInfo:
    value = os.getenv("BOT_TIMEZONE", "Europe/Kyiv").strip()
    try:
        return ZoneInfo(value)
    except Exception as error:
        raise ValueError(f"Unknown BOT_TIMEZONE: {value}") from error


async def send_daily_birthday_alert(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send today's birthday alerts to each affected user."""
    timezone = context.job.data["timezone"]
    today = datetime.now(timezone).date()
    birthdays = await storage.birthdays_for_date(today.year, today.month, today.day)
    grouped: dict[int, list[Birthday]] = defaultdict(list)
    for birthday in birthdays:
        grouped[birthday.user_id].append(birthday)

    for user_id, user_birthdays in grouped.items():
        names = "\n".join(f"• {_format_birthday(birthday)}" for birthday in user_birthdays)
        try:
            await context.bot.send_message(
                chat_id=user_id, text=f"🎂 Birthdays today:\n{names}"
            )
        except Exception:
            LOGGER.exception("Could not send birthday alert to user %s", user_id)


async def send_monthly_birthday_summary(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Send each registered user the birthdays occurring in the next month."""
    timezone = context.job.data["timezone"]
    today = datetime.now(timezone).date()
    next_month = 1 if today.month == 12 else today.month + 1
    users = await storage.list_users()

    for user in users:
        birthdays = await storage.list_birthdays(user.user_id, month=next_month)
        if birthdays:
            names = "\n".join(
                f"• {_format_birthday(birthday)}" for birthday in birthdays
            )
            text = f"📅 Birthdays in {next_month:02d}:\n{names}"
        else:
            text = f"📅 There are no birthdays saved for month {next_month:02d}."
        try:
            await context.bot.send_message(chat_id=user.user_id, text=text)
        except Exception:
            LOGGER.exception("Could not send birthday summary to user %s", user.user_id)


def schedule_birthday_jobs(application: Application) -> None:
    """Register recurring birthday jobs on the Telegram application's job queue."""
    timezone = _configured_timezone()
    daily_time = _configured_time("BIRTHDAY_ALERT_TIME", "09:00", timezone)
    summary_time = _configured_time("BIRTHDAY_SUMMARY_TIME", "09:05", timezone)
    if application.job_queue is None:
        raise RuntimeError(
            "Birthday scheduling requires python-telegram-bot[job-queue]"
        )
    job_data = {"timezone": timezone}
    application.job_queue.run_daily(
        send_daily_birthday_alert,
        time=daily_time,
        name="birthday-daily",
        data=job_data,
    )
    application.job_queue.run_monthly(
        send_monthly_birthday_summary,
        when=summary_time,
        day=1,
        name="birthday-monthly",
        data=job_data,
    )
