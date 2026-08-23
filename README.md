# Telegram Bot

A minimal Telegram bot built with Python 3.11+, [`python-telegram-bot`](https://python-telegram-bot.org/), and [`uv`](https://docs.astral.sh/uv/).

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Create the environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Put the token in `.env` as `TELEGRAM_BOT_TOKEN`.

## Run

```powershell
uv run telegram-bot
```

The bot uses long polling. It responds to `/start`, `/help`, and `/echo <text>`, and repeats regular text messages.

## Development

Add dependencies with `uv add <package>` and run commands inside the project with `uv run <command>`. The exact dependency versions are recorded in `uv.lock`.
