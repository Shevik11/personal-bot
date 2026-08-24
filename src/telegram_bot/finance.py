"""Finance expense entry workflow."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy.exc import SQLAlchemyError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from . import storage

FINANCE_BUTTON = "💰 Finance"
FINANCE_STATE = "finance_state"
STATE_EXPENSE = "finance_expense"
STATE_IMPORT = "finance_import"
MAX_MERCHANT_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 300
MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 1000


def _finance_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add expense", callback_data="finance:add")],
            [InlineKeyboardButton("📥 Import CSV", callback_data="finance:import")],
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
    if update.effective_user:
        await storage.register_user(update.effective_user.id)
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
    elif data == "finance:import":
        context.user_data[FINANCE_STATE] = STATE_IMPORT
        await query.edit_message_text(
            "Upload a UTF-8 CSV file with this header:\n\n"
            "date,amount,merchant,description\n\n"
            "Example row:\n"
            "2026-08-24,250.50,Silpo,groceries\n\n"
            "Dates must use YYYY-MM-DD. Existing identical expenses will be skipped.",
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

    clear_state(context)
    return False


def _parse_import_csv(content: bytes) -> list[tuple[str, int, str, str]]:
    """Validate an uploaded CSV before sending it to the database."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("The CSV file must use UTF-8 encoding") from error

    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("The CSV file must contain a header row")

    fields = {
        field.strip().casefold(): field
        for field in reader.fieldnames
        if field is not None
    }
    required = {"date", "amount", "merchant", "description"}
    missing = required - fields.keys()
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise ValueError(f"CSV header is missing: {missing_fields}")

    expenses: list[tuple[str, int, str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if row.get(None):
            raise ValueError(f"Row {row_number} has too many columns")
        values = {
            name: (row.get(original) or "").strip()
            for name, original in fields.items()
        }
        if not any(values.values()):
            continue
        try:
            expense_date = date.fromisoformat(values["date"]).isoformat()
            amount_minor = _parse_amount(values["amount"])
        except ValueError as error:
            raise ValueError(f"Row {row_number}: {error}") from error

        merchant = values["merchant"]
        description = values["description"]
        if not merchant or len(merchant) > MAX_MERCHANT_LENGTH:
            raise ValueError(
                f"Row {row_number}: merchant must be 1–{MAX_MERCHANT_LENGTH} characters"
            )
        if not description or len(description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Row {row_number}: description must be 1–{MAX_DESCRIPTION_LENGTH} characters"
            )
        expenses.append((expense_date, amount_minor, merchant, description))
        if len(expenses) > MAX_IMPORT_ROWS:
            raise ValueError(f"CSV cannot contain more than {MAX_IMPORT_ROWS} rows")

    if not expenses:
        raise ValueError("The CSV file does not contain any expense rows")
    return expenses


async def handle_finance_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Import a CSV document while the finance import flow is active."""
    if not update.message or not update.effective_user or not update.message.document:
        return False
    if context.user_data.get(FINANCE_STATE) != STATE_IMPORT:
        return False

    document = update.message.document
    if document.file_size and document.file_size > MAX_IMPORT_BYTES:
        await update.message.reply_text(
            "The CSV file is too large. The limit is 2 MB.",
            reply_markup=_cancel_markup(),
        )
        return True
    if not (document.file_name or "").casefold().endswith(".csv"):
        await update.message.reply_text(
            "Please upload a file with the .csv extension.",
            reply_markup=_cancel_markup(),
        )
        return True

    await update.message.reply_text("⏳ Importing expenses…")
    try:
        telegram_file = await context.bot.get_file(document.file_id)
        content = bytes(await telegram_file.download_as_bytearray())
        if len(content) > MAX_IMPORT_BYTES:
            raise ValueError("The CSV file is too large. The limit is 2 MB")
        expenses = _parse_import_csv(content)
        added, duplicates = await storage.import_expenses(
            update.effective_user.id, expenses
        )
    except (ValueError, UnicodeError, csv.Error) as error:
        await update.message.reply_text(
            f"I could not import that file: {error}.",
            reply_markup=_cancel_markup(),
        )
        return True
    except (TelegramError, SQLAlchemyError):
        await update.message.reply_text(
            "I could not import that file right now. Please try again later.",
            reply_markup=_cancel_markup(),
        )
        return True

    clear_state(context)
    await update.message.reply_text(
        f"✅ Import complete. Added: {added}. Skipped duplicates: {duplicates}.",
        reply_markup=_finance_menu_markup(),
    )
    return True
