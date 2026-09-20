from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import DateTime, Field, SQLModel

from app.schemas.file import _enum_values


class MilestoneStatus(StrEnum):
    """The three states US-16 counts. `StrEnum`, matching every other status
    enum here, so that the member and the string it stores compare equal."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class MilestoneCreate(SQLModel):
    title: str
    description: str = ""
    position: int = 0
    week: int | None = None
    due_date: date | None = None
    file_ids: list[UUID] = Field(default_factory=list)


class MilestoneUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    position: int | None = None
    week: int | None = None
    status: MilestoneStatus | None = None
    due_date: date | None = None
    file_ids: list[UUID] | None = None


class MilestoneRead(SQLModel):
    id: UUID
    course_id: UUID
    position: int
    title: str
    description: str
    week: int | None
    status: MilestoneStatus
    due_date: date | None
    file_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class Milestone(SQLModel, table=True):
    """One planned item on a course's roadmap -- CR-23, Gantt r42.

    The producer side (CRUD) is r51 and the dashboard that reads it is r55. This
    file is only the table, which is what F4 was blocked on: until today
    `grep "class Milestone"` returned nothing while `erd.mmd` had drawn the
    entity since 16 August.
    """

    id: UUID | None = Field(default_factory=uuid4, primary_key=True)

    # R20. PostgreSQL does not index a foreign key for you, and "give me this
    # course's roadmap" is the only query this table has.
    course_id: UUID = Field(foreign_key="course.id", ondelete="CASCADE", index=True)

    position: int
    title: str
    description: str = ""

    # The one nullable column the diagram marks as such: a milestone need not
    # belong to a teaching week.
    week: int | None = None

    status: MilestoneStatus = Field(
        default=MilestoneStatus.NOT_STARTED,
        sa_column=Column(
            # values_callable, or the type is built from the member NAMES and
            # stores 'NOT_STARTED' while every other layer says 'not_started'.
            # That is finding R25, and it does not announce itself: nothing
            # errors, the comparisons just stop being true.
            SAEnum(MilestoneStatus, values_callable=_enum_values, name="milestonestatus"),
            nullable=False,
        ),
    )

    due_date: date | None = None

    # JSONB rather than a junction table, and deliberately so -- `erd.mmd` says
    # as much on this line. A junction table buys referential integrity and the
    # reverse question ("which milestones attach this file?"); no user story
    # asks the reverse question, so only the cost would land.
    #
    # Two defaults because there are two ways in. `default_factory` covers rows
    # this application creates; `server_default` covers anything that reaches
    # the table without passing through it. With both, and NOT NULL, no reader
    # ever has to treat NULL and [] as different things.
    file_ids: list[UUID] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(UTC),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(UTC),
    )
