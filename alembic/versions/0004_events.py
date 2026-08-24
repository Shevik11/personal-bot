"""Add date-based calendar events."""

import sqlalchemy as sa

from alembic import op

revision = "0004_events"
down_revision = "0003_todo_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("end_date", sa.String(10), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["bot_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "events_by_user_dates",
        "events",
        ["user_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_index("events_by_user_dates", table_name="events")
    op.drop_table("events")
