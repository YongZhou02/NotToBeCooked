"""Production hybrid search over the frozen chunks. Retrieval only: no answer, no model call."""

NAME = "prod_hybrid"
DESCRIPTION = "Production hybrid search (apps/api) over the Postgres test database; returns the top 5 chunks, no answer."
NEEDS_DATABASE = True  # tells the runner to seed the test database before timing starts


async def answer(question: dict, tk) -> dict:
    return {"sources": await tk.prod_hybrid(question["question"], k=5)}
