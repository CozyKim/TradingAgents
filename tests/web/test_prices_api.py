"""API tests for /api/prices."""
from datetime import date

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint
from tradingagents_web.services import prices as prices_svc

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


def test_get_price_history(monkeypatch, app_with_test_db, client):
    fake = PriceHistoryResponse(
        ticker="AAPL",
        points=[
            PricePoint(
                date=date(2026, 4, 22),
                open=180.0,
                high=182.5,
                low=179.4,
                close=181.5,
                volume=12_345_678,
            ),
        ],
        last_close=181.5,
    )
    monkeypatch.setattr(prices_svc, "get_price_history", lambda t, days=90: fake)
    client = _login(app_with_test_db, client)
    r = client.get("/api/prices/aapl/history?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["last_close"] == 181.5


def test_get_price_history_requires_auth(client):
    r = client.get("/api/prices/AAPL/history")
    assert r.status_code == 401
