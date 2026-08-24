"""A small Telegram bot using long polling."""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .db import migrate_database
from .finance import FINANCE_BUTTON, finance_callback, finance_menu, handle_finance_text
from .shopping import (
    SHOPPING_BUTTON,
    handle_shopping_text,
    main_menu_markup,
    shopping_callback,
    shopping_notes,
)

LOGGER = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet a user and explain the available commands."""
    del context
    if update.message:
        await update.message.reply_text(
            "Hi! I am ready to help. Send me a message, or use /help to see "
            "what I can do.",
            reply_markup=main_menu_markup(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the bot's commands."""
    del context
    if update.message:
        await update.message.reply_text(
            "/start — welcome message\n"
            "/help — show this help\n"
            "/echo <text> — repeat text back to you\n"
            "/shopping — open shopping notes\n"
            "/finance — manage expenses and statistics"
        )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Repeat the text supplied to /echo."""
    if update.message:
        message = " ".join(context.args).strip()
        await update.message.reply_text(message or "Usage: /echo <text>")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to regular text messages."""
    if await handle_shopping_text(update, context):
        return
    if await handle_finance_text(update, context):
        return

    del context
    if update.message:
        await update.message.reply_text(
            f"You said: {update.message.text}\nTry /help, {SHOPPING_BUTTON}, or {FINANCE_BUTTON}."
        )


def build_application(token: str) -> Application:
    """Build the Telegram application and register its handlers."""
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("echo", echo))
    application.add_handler(CommandHandler("shopping", shopping_notes))
    application.add_handler(CommandHandler("finance", finance_menu))
    application.add_handler(
        MessageHandler(filters.Regex(f"^{SHOPPING_BUTTON}$"), shopping_notes)
    )
    application.add_handler(
        MessageHandler(filters.Regex(f"^{FINANCE_BUTTON}$"), finance_menu)
    )
    application.add_handler(
        CallbackQueryHandler(shopping_callback, pattern=r"^shopping:")
    )
    application.add_handler(
        CallbackQueryHandler(finance_callback, pattern=r"^finance:")
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    return application


def main() -> None:
    """Load configuration and start the bot with long polling."""
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and add "
            "your bot token."
        )

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    LOGGER.info("Starting Telegram bot")
    migrate_database()
    build_application(token).run_polling()
