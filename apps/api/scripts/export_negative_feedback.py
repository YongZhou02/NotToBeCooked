"""Export negative answer feedback with the question, answer, and retrieval snapshot.

Usage from apps/api:
    uv run python scripts/export_negative_feedback.py --output negative-feedback.json
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlmodel import col, select

from app.db.database import async_session_maker
from app.schemas.chat import ChatRole, Message
from app.schemas.feedback import AnswerFeedback, FeedbackRating


def _json_default(value: Any) -> str:
    return str(value)


async def export(output: Path) -> int:
    async with async_session_maker() as session:
        statement = (
            select(AnswerFeedback, Message)
            .join(Message, col(AnswerFeedback.message_id) == col(Message.id))
            .where(col(AnswerFeedback.rating) == FeedbackRating.NEGATIVE)
            .order_by(col(AnswerFeedback.created_at).asc())
        )
        rows = (await session.exec(statement)).all()

        records: list[dict[str, Any]] = []
        for feedback, answer in rows:
            question_statement = (
                select(Message)
                .where(
                    col(Message.conversation_id) == answer.conversation_id,
                    col(Message.role) == ChatRole.USER,
                    col(Message.created_at) <= answer.created_at,
                )
                .order_by(col(Message.created_at).desc())
                .limit(1)
            )
            question = (await session.exec(question_statement)).one_or_none()
            records.append(
                {
                    "feedback_id": feedback.id,
                    "message_id": answer.id,
                    "question": question.content if question else None,
                    "answer": answer.content,
                    "rating": feedback.rating.value,
                    "reason": feedback.reason.value if feedback.reason else None,
                    "comment": feedback.comment,
                    "citations": answer.citations,
                    "grounded": answer.grounded,
                    "scope_snapshot": answer.scope_snapshot,
                    "created_at": feedback.created_at,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(records, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("negative-feedback.json"),
        help="Destination JSON file",
    )
    args = parser.parse_args()
    count = asyncio.run(export(args.output))
    print(f"Exported {count} negative feedback record(s) to {args.output}")


if __name__ == "__main__":
    main()
