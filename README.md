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

## Shopping notes

Open `🛒 Shopping notes` or run `/shopping` to create and view notes. Notes are organized by product type. The bot starts each user with `Groceries`, `Household`, `Pharmacy`, and `Other`; you can also create custom product types.

Shopping notes are stored in `shopping_notes.db` by default. Set `SHOPPING_NOTES_DB` in `.env` to use a different path.

## Storage choice

SQLite is the primary storage for this bot. It is a better fit than one JSON file because it provides transactions, constraints, indexes, and efficient queries as more entities and relationships are added. JSON is still useful later for import/export or backups, but it should not be the main live database: updating nested data usually means rewriting the whole file and concurrent writes are harder to handle safely.

For the current single-process Telegram bot, SQLite is a good balance of simplicity and capability. If the bot later runs multiple replicas or needs high concurrent write throughput, migrate the storage layer to PostgreSQL rather than splitting the live data across JSON files.

## Docker

Build the image:

```powershell
docker build -t telegram-bot .
```

Run it with the token from `.env` and a named volume for persistent SQLite data:

```powershell
docker run -d --name telegram-bot --restart unless-stopped `
  --env-file .env `
  -v telegram_bot_data:/app/data `
  telegram-bot
```

The database is stored at `/app/data/shopping_notes.db` inside the container and remains available when the container is recreated.

## Development

Add dependencies with `uv add <package>` and run commands inside the project with `uv run <command>`. The exact dependency versions are recorded in `uv.lock`.
