"""Every table in the schema, reachable from one import.

Alembic's autogenerate compares the live database against `SQLModel.metadata`,
and a table only lands in that metadata when the module defining it is executed.
A table whose module is never imported is, as far as Alembic can tell, a table
that should not exist -- and it writes `op.drop_table` for it without asking.

`migrations/env.py` imports this module and nothing else. Adding a table means
adding one line here, instead of remembering that env.py exists.

`Chunk` is declared on a `DeclarativeBase` rather than on SQLModel, but that Base
sets `metadata = SQLModel.metadata` (see schemas/chunk.py), so one metadata
object still covers every table.
"""

from app.schemas import chat, chunk, course, file, folder, ingestion_run, milestone, user

# Re-exported so linters can see the imports are deliberate. Nothing reads these
# names; importing the modules for their side effect is the entire point.
__all__ = [
    "chat",
    "chunk",
    "course",
    "file",
    "folder",
    "ingestion_run",
    "milestone",
    "user",
]
