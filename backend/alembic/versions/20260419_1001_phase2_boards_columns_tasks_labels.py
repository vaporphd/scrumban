"""phase2_boards_columns_tasks_labels

Revision ID: 73cb93ca2565
Revises: fcecc869fd60
Create Date: 2026-04-19 10:01:09.290546+00:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "73cb93ca2565"
down_revision: str | None = "fcecc869fd60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SQLAlchemy creates the ENUM type implicitly during create_table.
# Alembic autogenerate does NOT add a matching DROP TYPE to downgrade —
# we do it explicitly below so round-trip stays clean (CLAUDE.md gotcha).
task_priority_enum = sa.Enum("low", "med", "high", "urgent", name="task_priority")


def upgrade() -> None:
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "columns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("wip_limit", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_columns_board_id"), "columns", ["board_id"], unique=False)
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
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
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_id", "name", name="uq_labels_board_id_name"),
    )
    op.create_index(op.f("ix_labels_board_id"), "labels", ["board_id"], unique=False)
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("column_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("priority", task_priority_enum, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Float(), nullable=False),
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
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["column_id"], ["columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_assignee_id_due_at", "tasks", ["assignee_id", "due_at"], unique=False)
    op.create_index("ix_tasks_column_id_position", "tasks", ["column_id", "position"], unique=False)
    op.create_table(
        "task_labels",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["label_id"], ["labels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "label_id"),
    )


def downgrade() -> None:
    op.drop_table("task_labels")
    op.drop_index("ix_tasks_column_id_position", table_name="tasks")
    op.drop_index("ix_tasks_assignee_id_due_at", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_labels_board_id"), table_name="labels")
    op.drop_table("labels")
    op.drop_index(op.f("ix_columns_board_id"), table_name="columns")
    op.drop_table("columns")
    op.drop_table("boards")
    # Drop the ENUM type after the table that used it is gone. Alembic
    # autogenerate doesn't emit this — see CLAUDE.md "Known gotchas".
    task_priority_enum.drop(op.get_bind(), checkfirst=True)
