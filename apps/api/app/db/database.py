# app/db/database.py
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401 -- register every table with SQLModel.metadata
from app.core.config import settings


def _json_default(value: Any) -> str:
    """The one type our JSONB columns hold that `json.dumps` refuses.

    Finding R35, 21 September 2026. Several models declare a JSONB column as
    `list[UUID]` -- `MESSAGE.mentioned_file_ids`, `MILESTONE.file_ids`. A JSONB
    column is written by calling `json.dumps` on the Python value, and
    `json.dumps(UUID(...))` raises

        TypeError: Object of type UUID is not JSON serializable

    so the INSERT never reaches the database. It is invisible in the type
    checker, because `list[UUID]` is exactly what the column claims to hold, and
    invisible to any test using a mocked session, because a mock serialises
    nothing. Measured against PGDialect_asyncpg, the dialect this project runs:
    `None` and `[]` commit, a list with one UUID in it does not.

    Deliberately NOT `default=str`. That would make every unserialisable object
    succeed, so a model instance left in a JSONB payload by mistake would be
    stored as `"<Course object at 0x7f...>"` and nobody would find out. Anything
    that is not a UUID still raises exactly as it did before.

    Reading the column back gives strings. Every response is built through a
    Read model that declares `list[UUID]` -- `MessageRead`, `MilestoneRead` --
    so pydantic turns them back on the way out, and the string form never
    leaves the database layer.
    """
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_serializer(value: Any) -> str:
    return json.dumps(value, default=_json_default)


def make_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Every engine in this project, including the ones the tests build.

    It exists so that a test engine cannot quietly differ from the running one.
    `json_serializer` below applies to every JSON and JSONB column on the engine
    it is passed to -- an engine built separately with a bare
    `create_async_engine(url)` does not get it, and a test on that engine would
    pass on code that fails in production. That is precisely how R35 stayed
    hidden, so the fix is not a keyword argument people must remember but a
    constructor they call.
    """
    return create_async_engine(
        url,
        echo=echo,
        future=True,
        json_serializer=_json_serializer,
    )


# 1. Create Async Engine (asyncpg)
engine = make_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO)

# 2. Define async session
async_session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# 3. Initialize DB and pgvector extension
async def init_db() -> None:
    # RETIRING -- both lines below leave this function on 19 Aug 2026, in the same
    # commit as the first migration. Not before: until that migration exists,
    # create_all is the only thing that builds tables, and removing it early
    # breaks every local database that gets recreated in the meantime.
    #
    # What that commit does:
    #   1. CREATE EXTENSION moves to the top of the first migration. It cannot
    #      stay here -- CI and any fresh machine run `alembic upgrade head`
    #      without ever calling init_db(), and CHUNK.embedding needs the
    #      extension in place before vector(1024) will build.
    #   2. create_all goes. It creates tables without writing anything to
    #      alembic_version, so Alembic then believes no migration has ever run
    #      and tries to create tables that already exist. Two record-keepers,
    #      neither aware of the other.
    #   3. Every database that already has tables gets `alembic stamp head` once,
    #      by hand -- Lim's, Calvin's, Bao Sheng's, and the OCI box.
    # After that, `alembic upgrade head` is a deploy step, not a startup step:
    # a failed migration should stop the deployment, not half-start the app.
    async with engine.begin() as conn:
        # Ensure pgvector extension is enabled in PostgreSQL
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(SQLModel.metadata.create_all)


# 4. Dependency for FastAPI Router Endpoints
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
