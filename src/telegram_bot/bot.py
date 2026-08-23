"""A small Telegram bot using long polling."""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

LOGGER = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet a user and explain the available commands."""
    del context
    if update.message:
        await update.message.reply_text(
            "Hi! I am ready to help. Send me a message, or use /help to see "
            "what I can do."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List the bot's commands."""
    del context
    if update.message:
        await update.message.reply_text(
            "/start — welcome message\n"
            "/help — show this help\n"
            "/echo <text> — repeat text back to you"
        )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Repeat the text supplied to /echo."""
    if update.message:
        message = " ".join(context.args).strip()
        await update.message.reply_text(message or "Usage: /echo <text>")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to regular text messages."""
    del context
    if update.message:
        await update.message.reply_text(
            f"You said: {update.message.text}\nTry /help for available commands."
        )


def build_application(token: str) -> Application:
    """Build the Telegram application and register its handlers."""
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("echo", echo))
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
    build_application(token).run_polling()
