"""SQLite persistence for shopping note categories and notes."""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_CATEGORIES = ("Groceries", "Household", "Pharmacy", "Other")


def _database_path() -> Path:
    configured_path = os.getenv("SHOPPING_NOTES_DB", "shopping_notes.db").strip()
    return Path(configured_path or "shopping_notes.db").expanduser()


def _connect() -> sqlite3.Connection:
    path = _database_path()
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create the shopping notes tables if they do not exist."""
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(user_id, name COLLATE NOCASE)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS notes_by_user_category
                ON notes(user_id, category_id, created_at);
            """
        )


def ensure_default_categories(user_id: int) -> None:
    """Create starter categories for a user without replacing custom ones."""
    with _connect() as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)",
            ((user_id, name) for name in DEFAULT_CATEGORIES),
        )


def list_categories(user_id: int) -> list[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute(
            "SELECT id, name FROM categories WHERE user_id = ? ORDER BY name COLLATE NOCASE",
            (user_id,),
        ).fetchall()


def get_category(user_id: int, category_id: int) -> sqlite3.Row | None:
    with _connect() as connection:
        return connection.execute(
            "SELECT id, name FROM categories WHERE user_id = ? AND id = ?",
            (user_id, category_id),
        ).fetchone()


def create_category(user_id: int, name: str) -> tuple[sqlite3.Row, bool]:
    """Create a category, returning its row and whether it was newly created."""
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
        category = connection.execute(
            "SELECT id, name FROM categories WHERE user_id = ? AND name = ? COLLATE NOCASE",
            (user_id, name),
        ).fetchone()

    if category is None:
        raise RuntimeError("The shopping note category could not be created")
    return category, cursor.rowcount == 1


def add_note(user_id: int, category_id: int, text: str) -> sqlite3.Row:
    """Add a note to one of the user's categories."""
    with _connect() as connection:
        category = connection.execute(
            "SELECT id FROM categories WHERE user_id = ? AND id = ?",
            (user_id, category_id),
        ).fetchone()
        if category is None:
            raise ValueError("That shopping note category does not exist")

        cursor = connection.execute(
            """
            INSERT INTO notes (user_id, category_id, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                category_id,
                text,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        return connection.execute(
            "SELECT id, text, created_at FROM notes WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()


def list_notes(user_id: int, category_id: int) -> list[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute(
            """
            SELECT id, text, created_at
            FROM notes
            WHERE user_id = ? AND category_id = ?
            ORDER BY id DESC
            """,
            (user_id, category_id),
        ).fetchall()
