"""Finance entry and natural-language statistics workflows."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from anthropic import AsyncAnthropic
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from . import storage

LOGGER = logging.getLogger(__name__)

FINANCE_BUTTON = "💰 Finance"
FINANCE_STATE = "finance_state"
STATE_EXPENSE = "finance_expense"
STATE_STATISTICS = "finance_statistics"
MAX_MERCHANT_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 300


class FinanceConfigurationError(RuntimeError):
    """Raised when Claude statistics are requested without configuration."""


def _finance_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add expense", callback_data="finance:add")],
            [
                InlineKeyboardButton(
                    "🤖 Ask statistics", callback_data="finance:statistics"
                )
            ],
        ]
    )


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖ Cancel", callback_data="finance:menu")]]
    )


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(FINANCE_STATE, None)


async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the finance menu."""
    clear_state(context)
    if update.message:
        await update.message.reply_text(
            "💰 Finance\n\nWhat would you like to do?",
            reply_markup=_finance_menu_markup(),
        )


async def finance_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle finance menu buttons."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data or ""
    if data == "finance:menu":
        clear_state(context)
        await query.edit_message_text(
            "💰 Finance\n\nWhat would you like to do?",
            reply_markup=_finance_menu_markup(),
        )
    elif data == "finance:add":
        context.user_data[FINANCE_STATE] = STATE_EXPENSE
        await query.edit_message_text(
            "Send an expense in this format:\n"
            "amount | merchant | what you bought\n\n"
            "Example: 250.50 | Сільпо | продукти\n"
            "To enter another date, use:\n"
            "YYYY-MM-DD | amount | merchant | what you bought",
            reply_markup=_cancel_markup(),
        )
    elif data == "finance:statistics":
        context.user_data[FINANCE_STATE] = STATE_STATISTICS
        await query.edit_message_text(
            "What would you like to know?\n\n"
            "Examples:\n"
            "• How much did I spend in Сільпо in August?\n"
            "• Show my spending by month this year.\n"
            "• What did I spend the most on?",
            reply_markup=_cancel_markup(),
        )


def _parse_amount(value: str) -> int:
    normalized = value.strip().replace(" ", "").replace("\u00a0", "")
    normalized = normalized.replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("Amount must be a positive number") from error

    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    minor = (amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    if minor > 100_000_000_00:
        raise ValueError("Amount is too large")
    return int(minor)


def _parse_expense(text: str) -> tuple[str, int, str, str]:
    parts = [part.strip() for part in text.split("|")]
    if len(parts) == 3:
        expense_date = datetime.now(UTC).date().isoformat()
        amount_text, merchant, description = parts
    elif len(parts) == 4:
        expense_date, amount_text, merchant, description = parts
        try:
            expense_date = date.fromisoformat(expense_date).isoformat()
        except ValueError as error:
            raise ValueError("Date must use YYYY-MM-DD format") from error
    else:
        raise ValueError("Use 3 fields, or 4 fields when including a date")

    if not merchant or len(merchant) > MAX_MERCHANT_LENGTH:
        raise ValueError("Merchant must be 1–100 characters")
    if not description or len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError("Description must be 1–300 characters")
    return expense_date, _parse_amount(amount_text), merchant, description


def _format_amount(amount_minor: int, currency: str = storage.DEFAULT_CURRENCY) -> str:
    return f"{amount_minor / 100:,.2f} {currency}"


async def handle_finance_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Consume text input when the user is in a finance workflow."""
    if not update.message or not update.effective_user:
        return False

    state = context.user_data.get(FINANCE_STATE)
    if not state:
        return False

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Please send some text, or press Cancel.")
        return True

    if state == STATE_EXPENSE:
        try:
            expense_date, amount_minor, merchant, description = _parse_expense(text)
        except ValueError as error:
            await update.message.reply_text(
                f"I could not save that expense: {error}.\n\n"
                "Try: 250.50 | Сільпо | продукти",
                reply_markup=_cancel_markup(),
            )
            return True

        expense = await storage.add_expense(
            update.effective_user.id,
            expense_date,
            amount_minor,
            merchant,
            description,
        )
        clear_state(context)
        await update.message.reply_text(
            "✅ Expense saved\n"
            f"{expense.expense_date}: {_format_amount(expense.amount_minor)}\n"
            f"{expense.merchant} — {expense.description}",
        )
        await update.message.reply_text(
            "What would you like to do next?", reply_markup=_finance_menu_markup()
        )
        return True

    if state == STATE_STATISTICS:
        clear_state(context)
        await update.message.reply_text("⏳ Checking your finance data…")
        try:
            answer = await ask_statistics(update.effective_user.id, text)
        except FinanceConfigurationError as error:
            answer = str(error)
        except Exception:
            LOGGER.exception("Claude finance statistics request failed")
            answer = "I could not check the statistics right now. Please try again later."
        await update.message.reply_text(answer, reply_markup=_finance_menu_markup())
        return True

    clear_state(context)
    return False


def _tool_definition() -> dict[str, Any]:
    return {
        "name": "get_finance_statistics",
        "description": (
            "Query the user's expense database. Use this for totals, averages, "
            "comparisons, or breakdowns by month, day, merchant, or purchased item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Inclusive start date in YYYY-MM-DD format.",
                },
                "end_date": {
                    "type": "string",
                    "description": "Inclusive end date in YYYY-MM-DD format.",
                },
                "merchant": {
                    "type": "string",
                    "description": "Optional case-insensitive merchant filter.",
                },
                "description": {
                    "type": "string",
                    "description": "Optional case-insensitive purchased-item filter.",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["none", "day", "month", "merchant", "item"],
                    "description": "How to break down the result, if requested.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of breakdown rows, from 1 to 50.",
                },
            },
        },
    }


def _tool_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Claude returned invalid finance filters")

    result: dict[str, Any] = {}
    for key in ("start_date", "end_date"):
        candidate = value.get(key)
        if candidate is not None:
            if not isinstance(candidate, str):
                raise ValueError("Finance dates must be strings")
            result[key] = date.fromisoformat(candidate).isoformat()
    for key in ("merchant", "description"):
        candidate = value.get(key)
        if candidate is not None:
            if not isinstance(candidate, str):
                raise ValueError("Finance filters must be strings")
            result[key] = candidate[:100]

    group_by = value.get("group_by", "none")
    if group_by not in {"none", "day", "month", "merchant", "item"}:
        raise ValueError("Claude returned invalid finance grouping")
    result["group_by"] = group_by

    limit = value.get("limit", 10)
    result["limit"] = int(limit) if isinstance(limit, (int, float)) else 10
    return result


def _text_response(message: Any) -> str:
    text = "\n".join(
        block.text
        for block in message.content
        if getattr(block, "type", None) == "text"
    ).strip()
    return text or "Claude did not return a text answer."


async def ask_statistics(user_id: int, question: str) -> str:
    """Ask Claude to select a safe statistics query and explain its result."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise FinanceConfigurationError(
            "Statistics are not configured yet. Add ANTHROPIC_API_KEY to .env."
        )

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    today = datetime.now(UTC).date().isoformat()
    system = (
        "You are a personal finance statistics assistant. Today is "
        f"{today}. Use the get_finance_statistics tool for every numeric answer. "
        "Never invent transactions or numbers. Amounts are integer minor units; "
        f"100 minor units equal 1 {storage.DEFAULT_CURRENCY}. "
        "Answer concisely in the user's language and mention the date range used."
    )

    async with AsyncAnthropic(api_key=api_key) as client:
        first = await client.messages.create(
            model=model,
            max_tokens=800,
            system=system,
            tools=[_tool_definition()],
            messages=[{"role": "user", "content": question}],
        )
        tool_use = next(
            (block for block in first.content if block.type == "tool_use"), None
        )
        if tool_use is None:
            return _text_response(first)

        filters = _tool_input(tool_use.input)
        statistics = await storage.finance_statistics(user_id, **filters)
        assistant_content = [
            block.model_dump() if hasattr(block, "model_dump") else block
            for block in first.content
        ]
        second = await client.messages.create(
            model=model,
            max_tokens=800,
            system=system,
            tools=[_tool_definition()],
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": assistant_content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(statistics),
                        }
                    ],
                },
            ],
        )
        return _text_response(second)
