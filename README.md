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

The application uses SQLAlchemy 2 ORM with async SQLite sessions. Alembic manages schema versions; the bot applies pending migrations at startup. To apply them manually:

```powershell
uv run alembic upgrade head
```

Runtime repositories use ORM queries, including the finance aggregate queries. The only SQL-like statements outside migrations are SQLite connection pragmas for foreign keys, WAL mode, and lock timeouts.

## Birthday reminders

Open `🎂 Birthdays` or run `/birthdays` to add, list, or delete birthday reminders. Add one with:

```text
Alex | 24.08
```

An optional birth year can be included as `Alex | 24.08.1990` or `Alex | 1990-08-24`. The bot sends birthday-day alerts at `BIRTHDAY_ALERT_TIME` and sends a list for the following month on the first day of each month at `BIRTHDAY_SUMMARY_TIME`. Both times use `BOT_TIMEZONE`; defaults are `09:00`, `09:05`, and `Europe/Kyiv`.

## To-do list

Open `✅ To-do list` or run `/todo` to manage your default personal task list. You can add tasks, view them, delete them manually, or press `✅ Complete`; completing a task deletes it from the list immediately.

## Events

Open `📅 Events` or run `/events` to save date-based events. A one-day event can be entered as:

```text
Doctor appointment | 2026-09-02
```

For an event lasting several days, use an inclusive start and end date:

```text
Mountains | 2026-08-29 | 2026-08-30
```

When browsing by day, a multi-day event appears on every date in its range, so the Mountains event is visible on both Saturday and Sunday.

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

## Finance checker

Open `💰 Finance` or run `/finance`.

To save an expense, use:

```text
250.50 | Сільпо | продукти
```

This uses today's date. To provide a date explicitly:

```text
2026-08-24 | 250.50 | Сільпо | продукти
```

Amounts are stored as integer minor units to avoid floating-point rounding errors. The default currency is UAH.

To ask for statistics, choose `🤖 Ask statistics` and write a question such as `How much did I spend in Сільпо in August?`. The bot sends Claude only the question and the resulting aggregates; Claude cannot execute arbitrary SQL or access the raw database. Set `ANTHROPIC_API_KEY` in `.env` to enable this feature. `CLAUDE_MODEL` can override the default model.

### Import the old workbook

The importer reads only the consolidated first sheet (`Всі місяці`) and skips exact duplicates. Run a dry-run first, then add `--apply` when the count looks right:

```powershell
uv run python scripts/import_expenses.py data/Витрати.xlsx --user-id 123
uv run python scripts/import_expenses.py data/Витрати.xlsx --user-id 123 --apply
```

Replace `123` with your Telegram user ID. The workbook in `data/` is ignored by Git and is not included in the Docker image.

## Development

Add dependencies with `uv add <package>` and run commands inside the project with `uv run <command>`. The exact dependency versions are recorded in `uv.lock`.
