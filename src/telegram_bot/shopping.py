"""Telegram UI and workflows for shopping notes."""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from . import storage
from .finance import FINANCE_BUTTON
from .models import Category, Note

SHOPPING_BUTTON = "🛒 Shopping notes"
SHOPPING_STATE = "shopping_state"
SELECTED_CATEGORY = "shopping_category_id"
STATE_NEW_CATEGORY = "new_category"
STATE_NOTE_TEXT = "note_text"
MAX_CATEGORY_LENGTH = 50
MAX_NOTE_LENGTH = 500


def main_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[SHOPPING_BUTTON], [FINANCE_BUTTON]],
        resize_keyboard=True,
        is_persistent=True,
    )


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖ Cancel", callback_data="shopping:menu")]]
    )


def _shopping_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Create note", callback_data="shopping:create")],
            [InlineKeyboardButton("📋 View notes", callback_data="shopping:view")],
        ]
    )


def _category_markup(
    categories: list[Category], action: str, include_new: bool = False
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                category.name,
                callback_data=f"shopping:{action}:category:{category.id}",
            )
        ]
        for category in categories
    ]
    if include_new:
        buttons.append(
            [
                InlineKeyboardButton(
                    "✚ Create product type", callback_data="shopping:create:new"
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton("⬅ Back", callback_data="shopping:menu")]
    )
    return InlineKeyboardMarkup(buttons)


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(SHOPPING_STATE, None)
    context.user_data.pop(SELECTED_CATEGORY, None)


async def shopping_notes(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Open the shopping notes menu."""
    clear_state(context)
    user = update.effective_user
    if not user or not update.message:
        return

    await storage.ensure_default_categories(user.id)
    await update.message.reply_text(
        "🛒 Shopping notes\n\nWhat would you like to do?",
        reply_markup=_shopping_menu_markup(),
    )


async def shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle every inline button belonging to the shopping notes menu."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    await query.answer()
    await storage.ensure_default_categories(user.id)
    data = query.data or ""

    if data == "shopping:menu":
        clear_state(context)
        await query.edit_message_text(
            "🛒 Shopping notes\n\nWhat would you like to do?",
            reply_markup=_shopping_menu_markup(),
        )
        return

    if data == "shopping:create":
        clear_state(context)
        categories = await storage.list_categories(user.id)
        await query.edit_message_text(
            "➕ Create note\n\nChoose a product type:",
            reply_markup=_category_markup(categories, "create", include_new=True),
        )
        return

    if data == "shopping:create:new":
        context.user_data[SHOPPING_STATE] = STATE_NEW_CATEGORY
        await query.edit_message_text(
            "Send the name of the new product type.\n"
            f"It can be up to {MAX_CATEGORY_LENGTH} characters.",
            reply_markup=_cancel_markup(),
        )
        return

    if data == "shopping:view":
        clear_state(context)
        categories = await storage.list_categories(user.id)
        await query.edit_message_text(
            "📋 View notes\n\nChoose a product type:",
            reply_markup=_category_markup(categories, "view"),
        )
        return

    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "shopping" or parts[2] != "category":
        return

    try:
        category_id = int(parts[3])
    except ValueError:
        return

    category = await storage.get_category(user.id, category_id)
    if category is None:
        await query.edit_message_text(
            "That product type is no longer available.",
            reply_markup=_shopping_menu_markup(),
        )
        return

    if parts[1] == "create":
        context.user_data[SHOPPING_STATE] = STATE_NOTE_TEXT
        context.user_data[SELECTED_CATEGORY] = category_id
        await query.edit_message_text(
            f"What do you want to buy in “{category.name}”?\n"
            f"Send one note, up to {MAX_NOTE_LENGTH} characters.",
            reply_markup=_cancel_markup(),
        )
        return

    if parts[1] == "view":
        clear_state(context)
        notes = await storage.list_notes(user.id, category_id)
        await _show_notes(query, context, category.name, notes)


async def _show_notes(
    query, context: ContextTypes.DEFAULT_TYPE, category_name: str, notes: list[Note]
) -> None:
    heading = f"📋 {category_name}\n\n"
    if not notes:
        await query.edit_message_text(
            heading + "There are no notes in this type yet.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="shopping:view")]]
            ),
        )
        return

    lines = [f"• {note.text}" for note in notes]
    message = heading + "\n".join(lines)
    # Telegram messages are limited to 4096 characters. Keep the first response
    # readable and send overflow as separate messages.
    chunks: list[str] = []
    while message:
        chunks.append(message[:3900])
        message = message[3900:]

    await query.edit_message_text(
        chunks[0],
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="shopping:view")]]
        ),
    )
    for chunk in chunks[1:]:
        await context.bot.send_message(chat_id=query.message.chat_id, text=chunk)


async def handle_shopping_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Consume text input when the user is in a shopping notes workflow."""
    if not update.message or not update.effective_user:
        return False

    state = context.user_data.get(SHOPPING_STATE)
    if not state:
        return False

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Please send some text, or press Cancel.")
        return True

    if state == STATE_NEW_CATEGORY:
        if len(text) > MAX_CATEGORY_LENGTH:
            await update.message.reply_text(
                f"That name is too long. Keep it under {MAX_CATEGORY_LENGTH} characters."
            )
            return True

        category, created = await storage.create_category(
            update.effective_user.id, text
        )
        if not created:
            await update.message.reply_text(
                f"The product type “{category.name}” already exists. "
                "Send another name or press Cancel."
            )
            return True

        context.user_data[SHOPPING_STATE] = STATE_NOTE_TEXT
        context.user_data[SELECTED_CATEGORY] = category.id
        await update.message.reply_text(
            f"Product type “{category.name}” created.\n"
            f"What do you want to buy in it? (Up to {MAX_NOTE_LENGTH} characters.)",
            reply_markup=_cancel_markup(),
        )
        return True

    if state == STATE_NOTE_TEXT:
        if len(text) > MAX_NOTE_LENGTH:
            await update.message.reply_text(
                f"That note is too long. Keep it under {MAX_NOTE_LENGTH} characters."
            )
            return True

        category_id = context.user_data.get(SELECTED_CATEGORY)
        if not isinstance(category_id, int):
            clear_state(context)
            await update.message.reply_text(
                "The note flow expired. Please open Shopping notes again.",
                reply_markup=main_menu_markup(),
            )
            return True

        category = await storage.get_category(update.effective_user.id, category_id)
        if category is None:
            clear_state(context)
            await update.message.reply_text(
                "That product type is no longer available.",
                reply_markup=main_menu_markup(),
            )
            return True

        await storage.add_note(update.effective_user.id, category_id, text)
        clear_state(context)
        await update.message.reply_text(
            f"✅ Saved in “{category.name}”: {text}",
            reply_markup=main_menu_markup(),
        )
        await update.message.reply_text(
            "What would you like to do next?", reply_markup=_shopping_menu_markup()
        )
        return True

    clear_state(context)
    return False
