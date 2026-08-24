"""Telegram workflows for date-based, including multi-day, events."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from . import storage
from .models import CalendarEvent

EVENTS_BUTTON = "📅 Events"
EVENTS_STATE = "events_state"
STATE_ADD = "events_add"
MAX_EVENT_TITLE_LENGTH = 200


def _menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add event", callback_data="events:add")],
            [InlineKeyboardButton("📅 Browse by day", callback_data="events:days")],
            [InlineKeyboardButton("📋 All upcoming", callback_data="events:all")],
            [InlineKeyboardButton("🗑 Delete event", callback_data="events:delete")],
        ]
    )


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖ Cancel", callback_data="events:menu")]]
    )


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(EVENTS_STATE, None)


def _parse_date(value: str) -> date:
    try:
        if len(value) == 10 and value[2] == ".":
            day_text, month_text, year_text = value.split(".")
            return date(int(year_text), int(month_text), int(day_text))
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Dates must use YYYY-MM-DD or DD.MM.YYYY format") from error


def _parse_event(text: str) -> tuple[str, str, str]:
    """Parse `title | date` or `title | start date | end date`."""
    parts = [part.strip() for part in text.split("|")]
    if len(parts) not in {2, 3}:
        raise ValueError("Use: Event | YYYY-MM-DD | YYYY-MM-DD")

    title = parts[0]
    if not title or len(title) > MAX_EVENT_TITLE_LENGTH:
        raise ValueError(f"Event title must be 1–{MAX_EVENT_TITLE_LENGTH} characters")

    start = _parse_date(parts[1])
    end = _parse_date(parts[2]) if len(parts) == 3 else start
    if end < start:
        raise ValueError("End date cannot be before start date")
    return title, start.isoformat(), end.isoformat()


def _today() -> date:
    return datetime.now().astimezone().date()


def _format_date(value: str) -> str:
    return _parse_date(value).strftime("%d.%m.%Y")


def _format_event(event: CalendarEvent) -> str:
    if event.start_date == event.end_date:
        dates = _format_date(event.start_date)
    else:
        dates = f"{_format_date(event.start_date)}–{_format_date(event.end_date)}"
    return f"{event.title} — {dates}"


async def events_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the user's events menu."""
    clear_state(context)
    user = update.effective_user
    if not user or not update.message:
        return
    await storage.register_user(user.id)
    await update.message.reply_text(
        "📅 Events\n\nWhat would you like to do?", reply_markup=_menu_markup()
    )


async def events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline buttons belonging to the events menu."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    await query.answer()
    await storage.register_user(user.id)
    data = query.data or ""

    if data == "events:menu":
        clear_state(context)
        await query.edit_message_text(
            "📅 Events\n\nWhat would you like to do?", reply_markup=_menu_markup()
        )
        return

    if data == "events:add":
        context.user_data[EVENTS_STATE] = STATE_ADD
        await query.edit_message_text(
            "Send an event in this format:\n"
            "Event | YYYY-MM-DD\n\n"
            "For a multi-day event, include an end date:\n"
            "Event | YYYY-MM-DD | YYYY-MM-DD\n\n"
            "Example: Mountains | 2026-08-29 | 2026-08-30",
            reply_markup=_cancel_markup(),
        )
        return

    if data == "events:days":
        clear_state(context)
        await _show_days(query, user.id)
        return

    if data == "events:all":
        clear_state(context)
        await _show_all(query, user.id)
        return

    if data == "events:delete":
        clear_state(context)
        events = await storage.list_events(user.id)
        await _show_delete_choices(query, events)
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "day":
        try:
            selected_date = _parse_date(parts[2])
        except ValueError:
            return
        await _show_day(query, user.id, selected_date)
        return

    if len(parts) == 4 and parts[1:3] == ["delete", "ask"]:
        event_id = _event_id(parts[3])
        if event_id is None:
            return
        event = await storage.get_event(user.id, event_id)
        if event is None:
            await query.edit_message_text(
                "That event no longer exists.", reply_markup=_menu_markup()
            )
            return
        await query.edit_message_text(
            f"Delete “{_format_event(event)}”?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Delete",
                            callback_data=f"events:delete:confirm:{event.id}",
                        ),
                        InlineKeyboardButton("Cancel", callback_data="events:menu"),
                    ]
                ]
            ),
        )
        return

    if len(parts) == 4 and parts[1:3] == ["delete", "confirm"]:
        event_id = _event_id(parts[3])
        if event_id is None:
            return
        deleted = await storage.delete_event(user.id, event_id)
        await query.edit_message_text(
            "✅ Event deleted." if deleted else "That event no longer exists.",
            reply_markup=_menu_markup(),
        )


def _event_id(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


async def _show_days(query, user_id: int) -> None:
    first_day = _today()
    last_day = first_day + timedelta(days=6)
    events = await storage.list_events(
        user_id, from_date=first_day.isoformat(), to_date=last_day.isoformat()
    )
    buttons = []
    for offset in range(7):
        selected = first_day + timedelta(days=offset)
        selected_iso = selected.isoformat()
        count = sum(
            event.start_date <= selected_iso <= event.end_date for event in events
        )
        label = selected.strftime("%a %d.%m") + (f" ({count})" if count else "")
        buttons.append(
            [
                InlineKeyboardButton(
                    label, callback_data=f"events:day:{selected_iso}"
                )
            ]
        )
    buttons.append([InlineKeyboardButton("⬅ Back", callback_data="events:menu")])
    await query.edit_message_text(
        "📅 Choose a day:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def _show_day(query, user_id: int, selected_date: date) -> None:
    selected_iso = selected_date.isoformat()
    events = await storage.events_on_date(user_id, selected_iso)
    buttons = [
        [
            InlineKeyboardButton(
                "🗑 Delete", callback_data=f"events:delete:ask:{event.id}"
            )
        ]
        for event in events
    ]
    buttons.append([InlineKeyboardButton("⬅ Days", callback_data="events:days")])
    text = f"📅 Events on {selected_date.strftime('%A %d.%m.%Y')}:"
    if events:
        text += "\n\n" + "\n".join(f"• {_format_event(event)}" for event in events)
    else:
        text += "\n\nThere are no events on this day."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def _show_all(query, user_id: int) -> None:
    events = await storage.list_events(user_id, from_date=_today().isoformat())
    buttons = [
        [
            InlineKeyboardButton(
                "🗑 Delete", callback_data=f"events:delete:ask:{event.id}"
            )
        ]
        for event in events
    ]
    buttons.append([InlineKeyboardButton("⬅ Back", callback_data="events:menu")])
    text = "📋 Upcoming events:"
    if events:
        text += "\n\n" + "\n".join(f"• {_format_event(event)}" for event in events)
    else:
        text += "\n\nThere are no upcoming events."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def _show_delete_choices(query, events: list[CalendarEvent]) -> None:
    if not events:
        await query.edit_message_text(
            "There are no events to delete.", reply_markup=_menu_markup()
        )
        return
    buttons = [
        [
            InlineKeyboardButton(
                _format_event(event), callback_data=f"events:delete:ask:{event.id}"
            )
        ]
        for event in events
    ]
    buttons.append([InlineKeyboardButton("⬅ Back", callback_data="events:menu")])
    await query.edit_message_text(
        "🗑 Choose an event to delete:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_events_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Consume text input when the user is adding an event."""
    if not update.message or not update.effective_user:
        return False
    if context.user_data.get(EVENTS_STATE) != STATE_ADD:
        return False

    try:
        title, start_date, end_date = _parse_event(update.message.text.strip())
    except ValueError as error:
        await update.message.reply_text(
            f"I could not save that event: {error}.\n\n"
            "Example: Mountains | 2026-08-29 | 2026-08-30",
            reply_markup=_cancel_markup(),
        )
        return True

    event = await storage.add_event(
        update.effective_user.id, title, start_date, end_date
    )
    clear_state(context)
    await update.message.reply_text(
        f"✅ Event saved: {_format_event(event)}", reply_markup=_menu_markup()
    )
    return True
