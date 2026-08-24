"""Add registered users and recurring birthdays."""

import sqlalchemy as sa

from alembic import op

revision = "0002_birthdays"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "birthdays",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("person_name", sa.String(100, collation="NOCASE"), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["bot_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "person_name",
            "month",
            "day",
            name="uq_birthdays_user_person_date",
        ),
    )
    op.create_index("birthdays_by_month_day", "birthdays", ["month", "day"])
    op.create_index("birthdays_by_user", "birthdays", ["user_id"])


def downgrade() -> None:
    op.drop_index("birthdays_by_user", table_name="birthdays")
    op.drop_index("birthdays_by_month_day", table_name="birthdays")
    op.drop_table("birthdays")
    op.drop_table("bot_users")
