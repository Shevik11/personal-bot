"""SQLAlchemy ORM models for bot data."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class BotUser(Base):
    __tablename__ = "bot_users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    birthdays: Mapped[list[Birthday]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    todo_items: Mapped[list[TodoItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    events: Mapped[list[CalendarEvent]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Birthday(Base):
    __tablename__ = "birthdays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.user_id", ondelete="CASCADE"), nullable=False
    )
    person_name: Mapped[str] = mapped_column(
        String(100, collation="NOCASE"), nullable=False
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    user: Mapped[BotUser] = relationship(back_populates="birthdays")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "person_name",
            "month",
            "day",
            name="uq_birthdays_user_person_date",
        ),
        Index("birthdays_by_month_day", "month", "day"),
        Index("birthdays_by_user", "user_id"),
    )


class TodoItem(Base):
    __tablename__ = "todo_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.user_id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    user: Mapped[BotUser] = relationship(back_populates="todo_items")

    __table_args__ = (Index("todo_items_by_user", "user_id"),)


class CalendarEvent(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("bot_users.user_id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    user: Mapped[BotUser] = relationship(back_populates="events")

    __table_args__ = (
        Index("events_by_user_dates", "user_id", "start_date", "end_date"),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50, collation="NOCASE"), nullable=False)

    notes: Mapped[list[Note]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_categories_user_name", "user_id", "name", unique=True),
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    category: Mapped[Category] = relationship(back_populates="notes")

    __table_args__ = (
        Index("notes_by_user_category", "user_id", "category_id", "created_at"),
    )


class FinanceExpense(Base):
    __tablename__ = "finance_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    expense_date: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UAH")
    merchant: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_finance_expenses_amount_positive"),
        Index("finance_expenses_by_user_date", "user_id", "expense_date"),
        Index(
            "finance_expenses_by_user_merchant",
            "user_id",
            "merchant",
        ),
        Index(
            "finance_expenses_by_user_description",
            "user_id",
            "description",
        ),
    )
