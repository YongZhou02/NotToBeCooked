"""add answer feedback

Revision ID: a4f8c2d91b7e
Revises: d6693e225198
Create Date: 2026-11-07 09:45:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

feedback_rating = postgresql.ENUM(
    "positive",
    "negative",
    name="feedbackrating",
    create_type=False,
)

feedback_reason = postgresql.ENUM(
    "answer_incorrect",
    "retrieval_missed",
    "citation_unsupported",
    "answer_incomplete",
    "document_missing_answer",
    name="feedbackreason",
    create_type=False,
)

revision: str = "a4f8c2d91b7e"
down_revision: str | Sequence[str] | None = "d6693e225198"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    feedback_rating.create(op.get_bind(), checkfirst=True)
    feedback_reason.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "answerfeedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", feedback_rating, nullable=False),
        sa.Column("reason", feedback_reason, nullable=True),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "user_id",
            name="uq_answer_feedback_message_user",
        ),
    )
    op.create_index(
        op.f("ix_answerfeedback_message_id"),
        "answerfeedback",
        ["message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_answerfeedback_user_id"),
        "answerfeedback",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_answerfeedback_user_id"), table_name="answerfeedback")
    op.drop_index(op.f("ix_answerfeedback_message_id"), table_name="answerfeedback")
    op.drop_table("answerfeedback")
    feedback_reason.drop(op.get_bind(), checkfirst=True)
    feedback_rating.drop(op.get_bind(), checkfirst=True)
