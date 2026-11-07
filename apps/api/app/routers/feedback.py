from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.schemas.chat import ChatRole, Conversation, Message
from app.schemas.course import Course
from app.schemas.errors import ApiError
from app.schemas.feedback import (
    AnswerFeedback,
    AnswerFeedbackRead,
    AnswerFeedbackUpsert,
    FeedbackRating,
)

feedback_router = APIRouter()


def _user_id(user: dict) -> UUID:
    raw_user_id = user.get("sub")
    if not raw_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or tampered token"},
        )
    try:
        return UUID(str(raw_user_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid or tampered token"},
        ) from exc


async def _get_owned_assistant_message(
    message_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> Message:
    statement = (
        select(Message)
        .join(Conversation, col(Message.conversation_id) == col(Conversation.id))
        .join(Course, col(Conversation.course_id) == col(Course.id))
        .where(
            col(Message.id) == message_id,
            col(Message.role) == ChatRole.ASSISTANT,
            col(Course.user_id) == user_id,
        )
    )
    message = (await session.exec(statement)).one_or_none()
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MESSAGE_NOT_FOUND", "message": "Assistant message not found"},
        )
    return message


@feedback_router.put(
    "/messages/{message_id}/feedback",
    response_model=AnswerFeedbackRead,
    responses={
        401: {"model": ApiError, "description": "Missing, invalid or expired access token"},
        404: {"model": ApiError, "description": "Assistant message not found"},
    },
)
async def upsert_answer_feedback(
    message_id: UUID,
    payload: AnswerFeedbackUpsert,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    user_id = _user_id(user)
    await _get_owned_assistant_message(message_id, user_id, session)

    if payload.rating == FeedbackRating.POSITIVE and payload.reason is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_FEEDBACK",
                "message": "Positive feedback cannot include a negative reason",
            },
        )

    statement = select(AnswerFeedback).where(
        col(AnswerFeedback.message_id) == message_id,
        col(AnswerFeedback.user_id) == user_id,
    )
    feedback = (await session.exec(statement)).one_or_none()
    clean_comment = payload.comment.strip() if payload.comment else None

    if feedback is None:
        feedback = AnswerFeedback(
            message_id=message_id,
            user_id=user_id,
            rating=payload.rating,
            reason=payload.reason,
            comment=clean_comment or None,
        )
        session.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.reason = payload.reason
        feedback.comment = clean_comment or None
        feedback.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(feedback)
    return AnswerFeedbackRead.model_validate(feedback)


@feedback_router.get(
    "/messages/{message_id}/feedback",
    response_model=AnswerFeedbackRead,
    responses={
        401: {"model": ApiError, "description": "Missing, invalid or expired access token"},
        404: {"model": ApiError, "description": "Message or feedback not found"},
    },
)
async def get_answer_feedback(
    message_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
):
    user_id = _user_id(user)
    await _get_owned_assistant_message(message_id, user_id, session)

    statement = select(AnswerFeedback).where(
        col(AnswerFeedback.message_id) == message_id,
        col(AnswerFeedback.user_id) == user_id,
    )
    feedback = (await session.exec(statement)).one_or_none()
    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FEEDBACK_NOT_FOUND", "message": "Feedback not found"},
        )
    return AnswerFeedbackRead.model_validate(feedback)
