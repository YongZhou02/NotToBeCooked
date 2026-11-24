"""rename answerfeedback to answer_feedback

Revision ID: 58cd633ee63b
Revises: a4f8c2d91b7e
Create Date: 2026-11-24 00:19:05.242128

"""

from collections.abc import Sequence

# All three noqa markers are for the same situation: a migration whose body is
# empty, or which touches no str column, leaves one of these imports unused and
# `pnpm verify` goes red on a file nobody has written a line of yet. `sqlmodel`
# is not in Alembic's stock template at all -- autogenerate emits
# sqlmodel.sql.sqltypes.AutoString for every str column and imports nothing, so
# without it a generated migration dies with NameError on first run.
#
# Note the submodule form `sqlmodel.sql.sqltypes`. Plain `import sqlmodel` runs
# fine but pyright reports `"sql" is not a known attribute of module "sqlmodel"`
# on every AutoString column, and `pnpm verify` runs pyright over migrations/.
import sqlalchemy as sa  # noqa: F401
import sqlmodel.sql.sqltypes  # noqa: F401
from alembic import op  # noqa: F401

# ---------------------------------------------------------------------------
# Four things autogenerate cannot write. Check all four before running this.
# Every one of them was hit for real on 20-22 Aug 2026 while writing r41.
#
# 1. IMPORTS for types it does not recognise. It renders them by full dotted
#    path -- `pgvector.sqlalchemy.vector.VECTOR`, `app.schemas.chunk.TSVector`
#    -- and imports neither. Fails with NameError before opening a connection.
#    Import the submodule actually referenced, not the top-level package:
#    `import pgvector` leaves `pgvector.sqlalchemy` unbound.
#
# 2. EXTENSIONS. A model says a column is a Vector; it cannot say that the type
#    itself ships with an extension. A fresh database has none installed, and
#    `pgvector/pgvector` only puts the files on the server -- pg_extension is
#    per database. First line of upgrade():
#        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
#
# 3. DROPPING ENUM TYPES in downgrade(). op.drop_table removes the table and
#    nothing else; a PostgreSQL enum is a type in its own right and outlives
#    every table that used it, so the next upgrade dies on DuplicateObjectError.
#        sa.Enum(name="filestatus").drop(op.get_bind(), checkfirst=True)
#    Order matters: drop the tables first, or the type is still depended on.
#
# 4. REUSING AN ENUM that an earlier revision already created. This is the
#    quiet one -- it passes on a clean database and fails on every database
#    that ran the earlier revision separately, which is every teammate's.
#    Two lines, and both are needed, because two different actors emit
#    CREATE TYPE:
#
#        status = postgresql.ENUM("a", "b", name="filestatus", create_type=False)
#
#        def upgrade():
#            status.create(op.get_bind(), checkfirst=True)
#            op.create_table("milestone", sa.Column("status", status), ...)
#
#    create_type=False silences the one create_table fires on its own, which
#    never checks. checkfirst=True is the check, on the call you control.
#    Dropping either line brings the failure back: with create_type left True
#    the table build re-issues CREATE TYPE regardless of your checkfirst, and
#    with create_type=False alone the type is never created at all.
#    PostgreSQL has no CREATE TYPE IF NOT EXISTS -- checkfirst is the substitute.
# ---------------------------------------------------------------------------

# revision identifiers, used by Alembic.
revision: str = "58cd633ee63b"
down_revision: str | Sequence[str] | None = "a4f8c2d91b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every name a4f8c2d91b7e built from the old table name, read from pg_class and
# pg_constraint on a database at that revision. The unique constraint is not
# here: it was uq_answer_feedback_message_user from the start. Renaming the
# primary key renames its index with it.
_CONSTRAINTS = (
    ("answerfeedback_pkey", "answer_feedback_pkey"),
    ("answerfeedback_message_id_fkey", "answer_feedback_message_id_fkey"),
    ("answerfeedback_user_id_fkey", "answer_feedback_user_id_fkey"),
)
_INDEXES = (
    ("ix_answerfeedback_message_id", "ix_answer_feedback_message_id"),
    ("ix_answerfeedback_user_id", "ix_answer_feedback_user_id"),
)


def upgrade() -> None:
    """Rename `answerfeedback` to `answer_feedback`, like every other table.

    a4f8c2d91b7e created it under SQLModel's default name, the class name
    lowercased, because the model never set __tablename__. A rename rather than
    a rebuild, so the rows, the enum types and the foreign keys stay as they
    are. The constraints and indexes are renamed too, so a migrated database
    carries the names create_all gives a fresh one; `alembic check` compares
    indexes by name and would otherwise report both as drift.

    Alembic has no op for renaming an index or a constraint, hence the SQL.
    """
    op.rename_table("answerfeedback", "answer_feedback")
    for old, new in _CONSTRAINTS:
        op.execute(f"ALTER TABLE answer_feedback RENAME CONSTRAINT {old} TO {new}")
    for old, new in _INDEXES:
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")


def downgrade() -> None:
    """The same renames, backwards. Nothing is dropped, so nothing is lost."""
    for old, new in _INDEXES:
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    for old, new in _CONSTRAINTS:
        op.execute(f"ALTER TABLE answer_feedback RENAME CONSTRAINT {new} TO {old}")
    op.rename_table("answer_feedback", "answerfeedback")
