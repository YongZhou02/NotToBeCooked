from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.dependencies.auth import get_current_user
from app.schemas.course import Course
from app.schemas.file import File as FileRow
from app.schemas.milestone import (
    Milestone,
    MilestoneCreate,
    MilestoneRead,
    MilestoneUpdate,
)

milestones_router = APIRouter(dependencies=[Depends(get_current_user)])


async def _owned_course(course_id: UUID, user_id: UUID, session: AsyncSession) -> Course:
    """The course, if this user owns it. 404 otherwise -- never 403.

    A 403 would confirm the id exists and belongs to somebody else, which is a
    membership oracle: an attacker who can tell "not yours" from "not there" can
    enumerate every course id in the system. Same rule as `folder.py`.
    """
    statement = select(Course).where(
        col(Course.id) == course_id,
        col(Course.user_id) == user_id,
    )
    course = (await session.exec(statement)).first()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return course


async def _owned_milestone(
    course_id: UUID, milestone_id: UUID, user_id: UUID, session: AsyncSession
) -> Milestone:
    """One milestone, joined through COURSE so ownership is checked in the query.

    Joining rather than fetching-then-comparing means there is no window in which
    a row belonging to someone else is in memory.
    """
    statement = (
        select(Milestone)
        .join(Course, col(Milestone.course_id) == col(Course.id))
        .where(
            col(Milestone.id) == milestone_id,
            col(Milestone.course_id) == course_id,
            col(Course.user_id) == user_id,
        )
    )
    milestone = (await session.exec(statement)).first()
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milestone not found",
        )
    return milestone


async def _checked_file_ids(
    file_ids: list[UUID], course_id: UUID, session: AsyncSession
) -> list[str]:
    """Validate the attachments, then hand back the form the column can store.

    Two things happen here and both are necessary.

    FIRST, the ids are checked against this course. `erd.mmd` calls MILESTONE.
    file_ids "deliberately not a join table", and the price of that decision is
    that PostgreSQL enforces no foreign key on the contents -- any uuid at all
    can be written into a JSONB array, including one belonging to another user's
    course. Without this check the attachment list is an unchecked reference.

    SECOND, the uuids are turned into strings. A JSONB column is serialised with
    `json.dumps`, and `json.dumps(UUID(...))` raises
    `TypeError: Object of type UUID is not JSON serializable`. Measured on
    2026-09-21 against `PGDialect_asyncpg`, which is the dialect this project
    runs. Reading the column back gives strings, and `MilestoneRead.file_ids`
    is declared `list[UUID]`, so pydantic converts them back on the way out --
    the string form never leaves this layer.
    """
    if not file_ids:
        return []

    unique_ids = list(dict.fromkeys(file_ids))
    statement = select(FileRow.id).where(
        col(FileRow.id).in_(unique_ids),
        col(FileRow.course_id) == course_id,
    )
    found = set((await session.exec(statement)).all())

    missing = [file_id for file_id in unique_ids if file_id not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found in this course: {missing[0]}",
        )

    return [str(file_id) for file_id in unique_ids]


@milestones_router.post(
    "/{course_id}/milestones",
    response_model=MilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    course_id: UUID,
    data: MilestoneCreate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> MilestoneRead:
    user_id = UUID(user["sub"])
    await _owned_course(course_id, user_id, session)

    milestone = Milestone(
        course_id=course_id,
        position=data.position,
        title=data.title,
        description=data.description,
        week=data.week,
        due_date=data.due_date,
    )
    # Assigned after construction rather than in the call above: the constructor
    # is typed `list[UUID]` and what the column needs is `list[str]`.
    milestone.file_ids = await _checked_file_ids(data.file_ids, course_id, session)  # type: ignore[assignment]

    session.add(milestone)
    await session.commit()
    await session.refresh(milestone)
    return MilestoneRead.model_validate(milestone)


@milestones_router.get(
    "/{course_id}/milestones",
    response_model=list[MilestoneRead],
)
async def list_milestones(
    course_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> list[MilestoneRead]:
    user_id = UUID(user["sub"])
    await _owned_course(course_id, user_id, session)

    # Ordered by `position`, which is what the column is for -- a roadmap read in
    # insertion order is not a roadmap. `id` breaks the tie so that two
    # milestones sharing a position keep a stable order between requests rather
    # than coming back in whatever sequence the planner chose.
    statement = (
        select(Milestone)
        .where(col(Milestone.course_id) == course_id)
        .order_by(col(Milestone.position), col(Milestone.id))
    )
    milestones = (await session.exec(statement)).all()
    return [MilestoneRead.model_validate(milestone) for milestone in milestones]


@milestones_router.get(
    "/{course_id}/milestones/{milestone_id}",
    response_model=MilestoneRead,
    status_code=status.HTTP_200_OK,
)
async def get_milestone(
    course_id: UUID,
    milestone_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> MilestoneRead:
    user_id = UUID(user["sub"])
    milestone = await _owned_milestone(course_id, milestone_id, user_id, session)
    return MilestoneRead.model_validate(milestone)


@milestones_router.patch(
    "/{course_id}/milestones/{milestone_id}",
    response_model=MilestoneRead,
)
async def update_milestone(
    course_id: UUID,
    milestone_id: UUID,
    data: MilestoneUpdate,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> MilestoneRead:
    user_id = UUID(user["sub"])
    milestone = await _owned_milestone(course_id, milestone_id, user_id, session)

    # `exclude_unset=True`, and not the `if data.x is not None` chain the other
    # routers use. Every field of MilestoneUpdate defaults to None, so that chain
    # cannot tell "the client did not mention week" from "the client is clearing
    # week". MILESTONE has two nullable columns a user can legitimately want
    # emptied -- `week` and `due_date` -- and with the None chain there is no
    # request that empties them. exclude_unset asks a different question: which
    # keys were present in the JSON body.
    changes = data.model_dump(exclude_unset=True)

    if "file_ids" in changes:
        file_ids = changes.pop("file_ids")
        milestone.file_ids = (  # type: ignore[assignment]
            await _checked_file_ids(file_ids, course_id, session) if file_ids else []
        )

    for field, value in changes.items():
        setattr(milestone, field, value)

    # Set by hand because the column has no `onupdate`: `default_factory` runs
    # once, when the row is built, and never again. Without this line a roadmap
    # edited every week keeps reporting the date it was created.
    milestone.updated_at = datetime.now(UTC)

    session.add(milestone)
    await session.commit()
    await session.refresh(milestone)
    return MilestoneRead.model_validate(milestone)


@milestones_router.delete(
    "/{course_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_milestone(
    course_id: UUID,
    milestone_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: dict = Depends(get_current_user),
) -> None:
    user_id = UUID(user["sub"])
    milestone = await _owned_milestone(course_id, milestone_id, user_id, session)

    # No emptiness check, unlike `delete_folder`. A folder owns the rows beneath
    # it and deleting one silently would orphan files; a milestone owns nothing.
    # `file_ids` is a list of references, and removing the milestone removes the
    # references, not the files.
    await session.delete(milestone)
    await session.commit()
    return None
