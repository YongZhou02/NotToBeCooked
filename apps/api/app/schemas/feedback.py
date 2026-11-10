from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.schemas.file import _enum_values


class FeedbackRating(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class FeedbackReason(Enum):
    ANSWER_INCORRECT = "answer_incorrect"
    RETRIEVAL_MISSED = "retrieval_missed"
    CITATION_UNSUPPORTED = "citation_unsupported"
    ANSWER_INCOMPLETE = "answer_incomplete"
    DOCUMENT_MISSING_ANSWER = "document_missing_answer"


class AnswerFeedback(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "user_id",
            name="uq_answer_feedback_message_user",
        ),
    )

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(
        foreign_key="message.id",
        ondelete="CASCADE",
        index=True,
    )
    user_id: UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    rating: FeedbackRating = Field(
        sa_column=Column(
            SAEnum(
                FeedbackRating,
                values_callable=_enum_values,
                name="feedbackrating",
            ),
            nullable=False,
        )
    )
    reason: FeedbackReason | None = Field(
        default=None,
        sa_column=Column(
            SAEnum(
                FeedbackReason,
                values_callable=_enum_values,
                name="feedbackreason",
            ),
            nullable=True,
        ),
    )
    comment: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AnswerFeedbackUpsert(SQLModel):
    rating: FeedbackRating
    reason: FeedbackReason | None = None
    comment: str | None = Field(default=None, max_length=1000)


class AnswerFeedbackRead(SQLModel):
    id: UUID
    message_id: UUID
    rating: FeedbackRating
    reason: FeedbackReason | None
    comment: str | None
    created_at: datetime
    updated_at: datetime
