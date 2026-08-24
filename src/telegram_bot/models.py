"""SQLAlchemy ORM models for bot data."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


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
