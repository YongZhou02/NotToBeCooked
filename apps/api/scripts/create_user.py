#!/usr/bin/env python3
"""Create one account on a server where registration is closed.

    uv run python scripts/create_user.py someone@example.com "Display Name"

Prints a random password once. It is not stored anywhere else, so hand it to
the person straight away; nothing can show it again.

Why this exists: the public deployment sets ALLOW_REGISTRATION=false, because
every account there spends the team's shared Gemini quota. Accounts are made
the same way POST /auth/register makes them -- one USER row plus its Unsorted
course in one transaction (finding R15) -- so an account made here and one made
through the API cannot differ.
"""

import asyncio
import secrets
import sys
from uuid import uuid4

from sqlmodel import col, select

from app.db.database import async_session_maker
from app.routers.auth import build_unsorted_course, ph
from app.schemas.user import User


def random_password() -> str:
    # The register form requires one capital letter; token_urlsafe alone may
    # not contain one.
    return "N" + secrets.token_urlsafe(12)


async def main(email: str, display_name: str) -> int:
    async with async_session_maker() as session:
        existing = (await session.exec(select(User).where(col(User.email) == email))).first()
        if existing is not None:
            print(f"{email} already has an account.", file=sys.stderr)
            return 1

        password = random_password()
        user_id = uuid4()
        session.add(
            User(
                id=user_id,
                email=email,
                display_name=display_name,
                hashed_password=ph.hash(password.encode("utf-8")),
            )
        )
        await session.flush()
        session.add(build_unsorted_course(user_id))
        await session.commit()

    print(f"Created {email}. Password (shown once): {password}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
