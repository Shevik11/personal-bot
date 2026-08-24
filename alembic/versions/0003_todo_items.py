"""Add per-user todo items."""

import sqlalchemy as sa

from alembic import op

revision = "0003_todo_items"
down_revision = "0002_birthdays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todo_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["bot_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("todo_items_by_user", "todo_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("todo_items_by_user", table_name="todo_items")
    op.drop_table("todo_items")
