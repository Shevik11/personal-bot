"""Create the current bot tables without replacing existing data."""

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_index(bind, table: str, name: str) -> bool:
    return name in {item["name"] for item in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(50, collation="NOCASE"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_categories_user_name"),
        )

    if not _has_table(bind, "notes"):
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.ForeignKeyConstraint(
                ["category_id"], ["categories.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(bind, "finance_expenses"):
        op.create_table(
            "finance_expenses",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expense_date", sa.String(10), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="UAH"),
            sa.Column("merchant", sa.String(100), nullable=False),
            sa.Column("description", sa.String(300), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.CheckConstraint(
                "amount_minor > 0", name="ck_finance_expenses_amount_positive"
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    indexes = (
        ("notes", "notes_by_user_category", ["user_id", "category_id", "created_at"]),
        (
            "finance_expenses",
            "finance_expenses_by_user_date",
            ["user_id", "expense_date"],
        ),
        (
            "finance_expenses",
            "finance_expenses_by_user_merchant",
            ["user_id", "merchant"],
        ),
        (
            "finance_expenses",
            "finance_expenses_by_user_description",
            ["user_id", "description"],
        ),
    )
    for table, name, columns in indexes:
        if not _has_index(bind, table, name):
            op.create_index(name, table, columns)


def downgrade() -> None:
    op.drop_index(
        "finance_expenses_by_user_description", table_name="finance_expenses"
    )
    op.drop_index("finance_expenses_by_user_merchant", table_name="finance_expenses")
    op.drop_index("finance_expenses_by_user_date", table_name="finance_expenses")
    op.drop_index("notes_by_user_category", table_name="notes")
    op.drop_table("finance_expenses")
    op.drop_table("notes")
    op.drop_table("categories")
