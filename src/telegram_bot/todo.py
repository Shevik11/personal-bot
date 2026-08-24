"""Telegram workflows for each user's default todo list."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from . import storage
from .models import TodoItem

TODO_BUTTON = "✅ To-do list"
TODO_STATE = "todo_state"
STATE_ADD = "todo_add"
MAX_TODO_LENGTH = 500


def _menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add task", callback_data="todo:add")],
            [InlineKeyboardButton("📋 View tasks", callback_data="todo:list")],
            [InlineKeyboardButton("🗑 Delete task", callback_data="todo:delete")],
        ]
    )


def _cancel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✖ Cancel", callback_data="todo:menu")]]
    )


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(TODO_STATE, None)


def _task_label(todo: TodoItem) -> str:
    return f"{todo.id}. {todo.text}"


async def todo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the user's default todo list."""
    clear_state(context)
    user = update.effective_user
    if not user or not update.message:
        return
    await storage.register_user(user.id)
    await update.message.reply_text(
        "✅ To-do list\n\nWhat would you like to do?", reply_markup=_menu_markup()
    )


async def todo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline buttons belonging to the todo list."""
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    await query.answer()
    await storage.register_user(user.id)
    data = query.data or ""

    if data == "todo:menu":
        clear_state(context)
        await query.edit_message_text(
            "✅ To-do list\n\nWhat would you like to do?", reply_markup=_menu_markup()
        )
        return

    if data == "todo:add":
        context.user_data[TODO_STATE] = STATE_ADD
        await query.edit_message_text(
            f"Send the task you want to add (up to {MAX_TODO_LENGTH} characters).",
            reply_markup=_cancel_markup(),
        )
        return

    if data == "todo:list":
        clear_state(context)
        todos = await storage.list_todos(user.id)
        await _show_todos(query, todos)
        return

    if data == "todo:delete":
        clear_state(context)
        todos = await storage.list_todos(user.id)
        if not todos:
            await query.edit_message_text(
                "Your to-do list is empty.", reply_markup=_menu_markup()
            )
            return
        buttons = [
            [
                InlineKeyboardButton(
                    _task_label(todo), callback_data=f"todo:delete:ask:{todo.id}"
                )
            ]
            for todo in todos
        ]
        buttons.append([InlineKeyboardButton("⬅ Back", callback_data="todo:menu")])
        await query.edit_message_text(
            "🗑 Choose a task to delete:", reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    parts = data.split(":")
    if len(parts) == 3 and parts[1] == "complete":
        todo_id = _todo_id(parts[2])
        if todo_id is None:
            return
        deleted = await storage.delete_todo(user.id, todo_id)
        await query.edit_message_text(
            "✅ Task completed and removed."
            if deleted
            else "That task no longer exists.",
            reply_markup=_menu_markup(),
        )
        return

    if len(parts) == 4 and parts[1:3] == ["delete", "ask"]:
        todo_id = _todo_id(parts[3])
        if todo_id is None:
            return
        todo = await storage.get_todo(user.id, todo_id)
        if todo is None:
            await query.edit_message_text(
                "That task no longer exists.", reply_markup=_menu_markup()
            )
            return
        await query.edit_message_text(
            f"Delete “{todo.text}”?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ Delete",
                            callback_data=f"todo:delete:confirm:{todo.id}",
                        ),
                        InlineKeyboardButton("Cancel", callback_data="todo:delete"),
                    ]
                ]
            ),
        )
        return

    if len(parts) == 4 and parts[1:3] == ["delete", "confirm"]:
        todo_id = _todo_id(parts[3])
        if todo_id is None:
            return
        deleted = await storage.delete_todo(user.id, todo_id)
        await query.edit_message_text(
            "✅ Task deleted." if deleted else "That task no longer exists.",
            reply_markup=_menu_markup(),
        )


def _todo_id(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


async def _show_todos(query, todos: list[TodoItem]) -> None:
    if not todos:
        await query.edit_message_text(
            "📋 Your to-do list is empty.", reply_markup=_menu_markup()
        )
        return

    buttons = [
        [
            InlineKeyboardButton(
                "✅ Complete", callback_data=f"todo:complete:{todo.id}"
            ),
            InlineKeyboardButton("🗑 Delete", callback_data=f"todo:delete:ask:{todo.id}"),
        ]
        for todo in todos
    ]
    await query.edit_message_text(
        "📋 Your tasks:\n\n" + "\n".join(_task_label(todo) for todo in todos),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_todo_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Consume text input when the user is adding a todo item."""
    if not update.message or not update.effective_user:
        return False
    if context.user_data.get(TODO_STATE) != STATE_ADD:
        return False

    text = update.message.text.strip()
    if not text or len(text) > MAX_TODO_LENGTH:
        await update.message.reply_text(
            f"Task must be between 1 and {MAX_TODO_LENGTH} characters.",
            reply_markup=_cancel_markup(),
        )
        return True

    todo = await storage.add_todo(update.effective_user.id, text)
    clear_state(context)
    await update.message.reply_text(
        f"✅ Task added: {_task_label(todo)}", reply_markup=_menu_markup()
    )
    return True
