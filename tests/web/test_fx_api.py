"""API tests for /api/fx."""
from datetime import date, datetime, timezone

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.schemas.fx import FxRate
from tradingagents_web.services import fx as fx_svc

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_get_usd_krw(monkeypatch, app_with_test_db, client):
    fake = FxRate(
        pair="USDKRW",
        rate=1382.1,
        as_of=date(2026, 5, 5),
        fetched_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(fx_svc, "get_usd_krw_rate", lambda: fake)
    client = _login(app_with_test_db, client)

    r = client.get("/api/fx/usd-krw")
    assert r.status_code == 200
    body = r.json()
    assert body["pair"] == "USDKRW"
    assert body["rate"] == 1382.1
    assert body["as_of"] == "2026-05-05"


def test_get_usd_krw_requires_auth(client):
    r = client.get("/api/fx/usd-krw")
    assert r.status_code == 401
