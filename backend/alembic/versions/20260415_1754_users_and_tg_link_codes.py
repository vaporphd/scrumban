"""users_and_tg_link_codes

Revision ID: 5130146827ca
Revises:
Create Date: 2026-04-15 17:54:51.917261+00:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "5130146827ca"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SQLAlchemy creates the ENUM type implicitly during create_table.
# Alembic autogenerate does NOT add a matching DROP TYPE to downgrade —
# we do it explicitly below so round-trip stays clean.
user_role_enum = sa.Enum("owner", "member", name="user_role")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("tg_username", sa.String(length=64), nullable=True),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tg_user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "tg_link_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_active_link_code_per_user",
        "tg_link_codes",
        ["user_id"],
        unique=True,
        postgresql_where="consumed_at IS NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_link_code_per_user",
        table_name="tg_link_codes",
        postgresql_where="consumed_at IS NULL",
    )
    op.drop_table("tg_link_codes")
    op.drop_table("users")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
