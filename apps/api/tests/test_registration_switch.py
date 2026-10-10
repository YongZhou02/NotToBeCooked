"""ALLOW_REGISTRATION=false closes POST /auth/register -- and only that.

The public deployment runs on the team's shared Gemini key, so an open sign-up
form there is an open quota. The check sits before the email lookup, so a closed
server answers every address the same way.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.db.database import get_session
from app.main import app


async def _no_database():
    # If the guard is in the right place, the handler never reaches the session.
    yield None


@pytest.mark.asyncio
async def test_closed_registration_is_403_before_touching_the_database(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REGISTRATION", False)
    app.dependency_overrides[get_session] = _no_database
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/auth/register",
                json={"email": "a@x.com", "password": "Passw0rd!x", "display_name": "A"},
            )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "REGISTRATION_CLOSED"
