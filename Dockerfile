FROM python:3.11-slim-bookworm

# Copy a pinned uv binary into the Python image.
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    SHOPPING_NOTES_DB=/app/data/shopping_notes.db

# Install the locked application environment without development dependencies.
COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY src ./src
COPY alembic ./alembic
RUN uv sync --locked --no-dev --no-editable

# Keep the database outside the image layer and run without root privileges.
RUN useradd --create-home --shell /usr/sbin/nologin bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app
USER bot

VOLUME ["/app/data"]

CMD ["/app/.venv/bin/telegram-bot"]
