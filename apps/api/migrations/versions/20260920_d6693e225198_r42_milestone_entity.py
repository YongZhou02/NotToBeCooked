"""r42 milestone entity

Revision ID: d6693e225198
Revises: cc7bd2052443
Create Date: 2026-09-20 23:15:58.404955

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
from sqlalchemy.dialects import postgresql
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

# Checklist item 4 above. `create_table` emits its own CREATE TYPE and never
# checks first; `create_type=False` silences that one, and the explicit
# `.create(..., checkfirst=True)` in upgrade() is the check we control. Both
# lines are needed -- dropping either brings the failure back on any database
# that has the type already.
milestone_status = postgresql.ENUM(
    "not_started",
    "in_progress",
    "completed",
    name="milestonestatus",
    create_type=False,
)

# revision identifiers, used by Alembic.
revision: str = "d6693e225198"
down_revision: str | Sequence[str] | None = "cc7bd2052443"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    milestone_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "milestone",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            milestone_status,
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "file_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["course.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_milestone_course_id"), "milestone", ["course_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_milestone_course_id"), table_name="milestone")
    op.drop_table("milestone")
    # Checklist item 3. A PostgreSQL enum is a type in its own right and
    # outlives every table that used it, so without this the next upgrade dies
    # on DuplicateObjectError. Tables first, or the type is still depended on.
    sa.Enum(name="milestonestatus").drop(op.get_bind(), checkfirst=True)
