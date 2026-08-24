"""Async ORM repositories for shopping notes and finance expenses."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime

from sqlalchemy import select

from . import db
from .models import (
    Birthday,
    BotUser,
    CalendarEvent,
    Category,
    FinanceExpense,
    Note,
    TodoItem,
)

DEFAULT_CATEGORIES = ("Groceries", "Household", "Pharmacy", "Other")
DEFAULT_CURRENCY = "UAH"


async def initialize_database() -> None:
    """Create missing tables from the SQLAlchemy metadata."""
    await db.initialize_database()


async def register_user(user_id: int) -> BotUser:
    """Register a Telegram user so scheduled messages have a recipient."""
    async with db.session_scope() as session:
        user = await session.get(BotUser, user_id)
        if user is None:
            user = BotUser(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            session.add(user)
            await session.flush()
        return user


async def list_users() -> list[BotUser]:
    async with db.session_scope() as session:
        result = await session.scalars(select(BotUser).order_by(BotUser.user_id))
        return list(result.all())


async def add_todo(user_id: int, text: str) -> TodoItem:
    async with db.session_scope() as session:
        user = await session.get(BotUser, user_id)
        if user is None:
            user = BotUser(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            session.add(user)
            await session.flush()

        todo = TodoItem(
            user_id=user_id,
            text=text,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        session.add(todo)
        await session.flush()
        return todo


async def list_todos(user_id: int) -> list[TodoItem]:
    async with db.session_scope() as session:
        result = await session.scalars(
            select(TodoItem)
            .where(TodoItem.user_id == user_id)
            .order_by(TodoItem.id)
        )
        return list(result.all())


async def get_todo(user_id: int, todo_id: int) -> TodoItem | None:
    async with db.session_scope() as session:
        return await session.scalar(
            select(TodoItem).where(
                TodoItem.user_id == user_id,
                TodoItem.id == todo_id,
            )
        )


async def delete_todo(user_id: int, todo_id: int) -> bool:
    async with db.session_scope() as session:
        todo = await session.scalar(
            select(TodoItem).where(
                TodoItem.user_id == user_id,
                TodoItem.id == todo_id,
            )
        )
        if todo is None:
            return False
        await session.delete(todo)
        return True


async def add_event(
    user_id: int, title: str, start_date: str, end_date: str
) -> CalendarEvent:
    async with db.session_scope() as session:
        user = await session.get(BotUser, user_id)
        if user is None:
            user = BotUser(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            session.add(user)
            await session.flush()

        event = CalendarEvent(
            user_id=user_id,
            title=title,
            start_date=start_date,
            end_date=end_date,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        session.add(event)
        await session.flush()
        return event


async def list_events(
    user_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[CalendarEvent]:
    async with db.session_scope() as session:
        query = select(CalendarEvent).where(CalendarEvent.user_id == user_id)
        if from_date is not None:
            query = query.where(CalendarEvent.end_date >= from_date)
        if to_date is not None:
            query = query.where(CalendarEvent.start_date <= to_date)
        result = await session.scalars(
            query.order_by(CalendarEvent.start_date, CalendarEvent.end_date, CalendarEvent.id)
        )
        return list(result.all())


async def get_event(user_id: int, event_id: int) -> CalendarEvent | None:
    async with db.session_scope() as session:
        return await session.scalar(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.id == event_id,
            )
        )


async def delete_event(user_id: int, event_id: int) -> bool:
    async with db.session_scope() as session:
        event = await session.scalar(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.id == event_id,
            )
        )
        if event is None:
            return False
        await session.delete(event)
        return True


async def events_on_date(user_id: int, event_date: str) -> list[CalendarEvent]:
    async with db.session_scope() as session:
        result = await session.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.start_date <= event_date,
                CalendarEvent.end_date >= event_date,
            )
            .order_by(CalendarEvent.start_date, CalendarEvent.end_date, CalendarEvent.id)
        )
        return list(result.all())


async def add_birthday(
    user_id: int,
    person_name: str,
    month: int,
    day: int,
    birth_year: int | None = None,
) -> tuple[Birthday, bool]:
    """Save a birthday, returning the record and whether it was new."""
    async with db.session_scope() as session:
        user = await session.get(BotUser, user_id)
        if user is None:
            user = BotUser(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            session.add(user)
            await session.flush()

        birthday = await session.scalar(
            select(Birthday).where(
                Birthday.user_id == user_id,
                Birthday.person_name == person_name,
                Birthday.month == month,
                Birthday.day == day,
            )
        )
        if birthday is not None:
            return birthday, False

        birthday = Birthday(
            user_id=user_id,
            person_name=person_name,
            month=month,
            day=day,
            birth_year=birth_year,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        session.add(birthday)
        await session.flush()
        return birthday, True


async def list_birthdays(
    user_id: int, month: int | None = None
) -> list[Birthday]:
    async with db.session_scope() as session:
        query = select(Birthday).where(Birthday.user_id == user_id)
        if month is not None:
            query = query.where(Birthday.month == month)
        result = await session.scalars(
            query.order_by(Birthday.month, Birthday.day, Birthday.person_name, Birthday.id)
        )
        return list(result.all())


async def get_birthday(user_id: int, birthday_id: int) -> Birthday | None:
    async with db.session_scope() as session:
        return await session.scalar(
            select(Birthday).where(
                Birthday.user_id == user_id,
                Birthday.id == birthday_id,
            )
        )


async def delete_birthday(user_id: int, birthday_id: int) -> bool:
    async with db.session_scope() as session:
        birthday = await session.scalar(
            select(Birthday).where(
                Birthday.user_id == user_id,
                Birthday.id == birthday_id,
            )
        )
        if birthday is None:
            return False
        await session.delete(birthday)
        return True


async def birthdays_for_date(year: int, month: int, day: int) -> list[Birthday]:
    """Find birthdays for a date, including Feb 29 on Feb 28 in non-leap years."""
    days = [day]
    if month == 2 and day == 28 and not calendar.isleap(year):
        days.append(29)
    async with db.session_scope() as session:
        result = await session.scalars(
            select(Birthday)
            .where(Birthday.month == month, Birthday.day.in_(days))
            .order_by(Birthday.user_id, Birthday.person_name, Birthday.id)
        )
        return list(result.all())


async def ensure_default_categories(user_id: int) -> None:
    """Create starter categories without replacing custom ones."""
    async with db.session_scope() as session:
        existing = {
            name.casefold()
            for name in (
                await session.scalars(
                    select(Category.name).where(Category.user_id == user_id)
                )
            ).all()
        }
        for name in DEFAULT_CATEGORIES:
            if name.casefold() not in existing:
                session.add(Category(user_id=user_id, name=name))


async def list_categories(user_id: int) -> list[Category]:
    async with db.session_scope() as session:
        result = await session.scalars(
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.name.collate("NOCASE"))
        )
        return list(result.all())


async def get_category(user_id: int, category_id: int) -> Category | None:
    async with db.session_scope() as session:
        return await session.scalar(
            select(Category).where(
                Category.user_id == user_id,
                Category.id == category_id,
            )
        )


async def create_category(user_id: int, name: str) -> tuple[Category, bool]:
    """Create a category, returning the category and whether it was new."""
    async with db.session_scope() as session:
        category = await session.scalar(
            select(Category).where(
                Category.user_id == user_id,
                Category.name == name,
            )
        )
        if category is not None:
            return category, False

        category = Category(user_id=user_id, name=name)
        session.add(category)
        await session.flush()
        return category, True


async def add_note(user_id: int, category_id: int, text: str) -> Note:
    async with db.session_scope() as session:
        category = await session.scalar(
            select(Category).where(
                Category.user_id == user_id,
                Category.id == category_id,
            )
        )
        if category is None:
            raise ValueError("That shopping note category does not exist")

        note = Note(
            user_id=user_id,
            category_id=category_id,
            text=text,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        session.add(note)
        await session.flush()
        return note


async def list_notes(user_id: int, category_id: int) -> list[Note]:
    async with db.session_scope() as session:
        result = await session.scalars(
            select(Note)
            .where(Note.user_id == user_id, Note.category_id == category_id)
            .order_by(Note.id.desc())
        )
        return list(result.all())


async def add_expense(
    user_id: int,
    expense_date: str,
    amount_minor: int,
    merchant: str,
    description: str,
    currency: str = DEFAULT_CURRENCY,
) -> FinanceExpense:
    """Persist one finance expense using integer minor currency units."""
    async with db.session_scope() as session:
        expense = FinanceExpense(
            user_id=user_id,
            expense_date=expense_date,
            amount_minor=amount_minor,
            currency=currency,
            merchant=merchant,
            description=description,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        session.add(expense)
        await session.flush()
        return expense


async def import_expenses(
    user_id: int,
    expenses: list[tuple[str, int, str, str]],
    currency: str = DEFAULT_CURRENCY,
) -> tuple[int, int]:
    """Import expenses atomically, returning added and duplicate counts."""
    added = 0
    duplicates = 0
    async with db.session_scope() as session:
        for expense_date, amount_minor, merchant, description in expenses:
            existing = await session.scalar(
                select(FinanceExpense.id)
                .where(
                    FinanceExpense.user_id == user_id,
                    FinanceExpense.expense_date == expense_date,
                    FinanceExpense.amount_minor == amount_minor,
                    FinanceExpense.currency == currency,
                    FinanceExpense.merchant == merchant,
                    FinanceExpense.description == description,
                )
                .limit(1)
            )
            if existing is not None:
                duplicates += 1
                continue

            session.add(
                FinanceExpense(
                    user_id=user_id,
                    expense_date=expense_date,
                    amount_minor=amount_minor,
                    currency=currency,
                    merchant=merchant,
                    description=description,
                    created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                )
            )
            added += 1
    return added, duplicates


async def expense_exists(
    user_id: int,
    expense_date: str,
    amount_minor: int,
    merchant: str,
    description: str,
    currency: str = DEFAULT_CURRENCY,
) -> bool:
    """Check whether an identical expense is already stored."""
    async with db.session_scope() as session:
        expense_id = await session.scalar(
            select(FinanceExpense.id)
            .where(
                FinanceExpense.user_id == user_id,
                FinanceExpense.expense_date == expense_date,
                FinanceExpense.amount_minor == amount_minor,
                FinanceExpense.currency == currency,
                FinanceExpense.merchant == merchant,
                FinanceExpense.description == description,
            )
            .limit(1)
        )
        return expense_id is not None
