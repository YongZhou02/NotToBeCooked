"""Test database wiring.

The one rule this file exists to enforce: **tests never touch the database named
in `DATABASE_URL`.**

`tests/test_upload.py` builds its schema with `SQLModel.metadata.drop_all`
followed by `create_all`, because what it checks is a row and the bytes on disk
agreeing -- mocking either half would test nothing. Pointed at the development
database, that is `pnpm test` silently deleting whatever the developer was
working with. It happened on 31 August 2026: a full ingest run (42 chunks, seven
minutes of parsing) was wiped by the next `pnpm verify`, and nothing in the
output said so.

So the URL is derived here, once, by appending a suffix to the database name.
The assertion below is the part that matters -- more than the naming convention,
because a name can be edited back and an assertion cannot be edited back by
accident.
"""

from collections.abc import AsyncGenerator

import asyncpg
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.db.database import make_engine

TEST_DB_SUFFIX = "_test"


def build_test_database_url() -> str:
    """`postgresql+asyncpg://.../not_to_be_cooked` -> `.../not_to_be_cooked_test`."""
    dev = make_url(settings.DATABASE_URL)
    if not dev.database:
        raise RuntimeError(f"DATABASE_URL names no database: {dev.render_as_string()}")

    test = dev.set(database=dev.database + TEST_DB_SUFFIX)

    # The suffix is non-empty, so this cannot fire today. It fires the day
    # someone rewrites the line above -- which is the only way this file ever
    # becomes dangerous again.
    if test.render_as_string(hide_password=False) == dev.render_as_string(hide_password=False):
        raise RuntimeError(
            "The test database URL resolved to the development database. "
            "Refusing to run: these tests drop every table."
        )
    return test.render_as_string(hide_password=False)


async def _create_database_if_missing(url: str) -> None:
    """CREATE DATABASE cannot run inside a transaction, so it goes through asyncpg
    directly rather than through SQLAlchemy's engine."""
    target = make_url(url)
    admin = await asyncpg.connect(
        host=target.host,
        port=target.port,
        user=target.username,
        password=target.password,
        database="postgres",
    )
    try:
        exists = await admin.fetchval(
            "select 1 from pg_database where datname = $1", target.database
        )
        if not exists:
            # Identifier, not a value -- it cannot be a bound parameter. The name
            # is built from DATABASE_URL plus a literal suffix, not from input.
            await admin.execute(f'CREATE DATABASE "{target.database}"')
    finally:
        await admin.close()


@pytest_asyncio.fixture(scope="session")
async def test_database_url() -> AsyncGenerator[str, None]:
    """The URL every database-backed test must use. Created once per session.

    The database is left in place afterwards. Dropping it would make the next run
    pay for CREATE DATABASE again, and there is nothing in it worth protecting --
    each test rebuilds the schema anyway.
    """
    url = build_test_database_url()
    await _create_database_if_missing(url)

    # CHUNK.embedding is vector(1024); create_all cannot build that column until
    # the extension exists. The development database got this from init_db(); a
    # freshly created test database has nothing.
    engine = make_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    await engine.dispose()

    yield url
