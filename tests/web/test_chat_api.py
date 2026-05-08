"""Chat API 라우트 회귀."""
from datetime import date

from tradingagents_web.models import Analysis, ChatMessage


def _seed_completed(db) -> Analysis:
    a = Analysis(
        run_id="r-api",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        decision="BUY",
        confidence=0.7,
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
        final_state={"market_report": "ok"},
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_post_turn_requires_login(client_unauth, db_session):
    a = _seed_completed(db_session)
    r = client_unauth.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "안녕"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 401


def test_post_turn_requires_csrf(auth_client, db_session):
    a = _seed_completed(db_session)
    r = auth_client.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "안녕"},
    )
    assert r.status_code == 403


def test_post_turn_409_when_not_completed(auth_client, db_session):
    a = _seed_completed(db_session)
    a.status = "running"
    db_session.commit()
    r = auth_client.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "안녕"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 409


def test_post_turn_creates_user_message_and_returns_turn_id(
    auth_client, db_session, monkeypatch
):
    a = _seed_completed(db_session)
    monkeypatch.setattr(
        "tradingagents_web.api.chat._spawn_turn_task",
        lambda **k: None,
    )
    r = auth_client.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "안녕"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 201
    tid = r.json()["turn_id"]
    msg = (
        db_session.query(ChatMessage)
        .filter_by(turn_id=tid, role="user")
        .one()
    )
    assert msg.content_blocks[0]["text"] == "안녕"


def test_get_messages_returns_persisted(auth_client, db_session):
    a = _seed_completed(db_session)
    for i in range(3):
        db_session.add(
            ChatMessage(
                analysis_id=a.id,
                turn_id=f"t{i}",
                sequence=i,
                role="user",
                content_blocks=[{"type": "text", "text": f"q{i}"}],
            )
        )
    db_session.commit()
    r = auth_client.get(f"/api/runs/{a.run_id}/chat/messages")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_post_turn_409_when_inflight(auth_client, db_session, monkeypatch):
    a = _seed_completed(db_session)
    monkeypatch.setattr(
        "tradingagents_web.api.chat._spawn_turn_task",
        lambda **k: None,
    )
    monkeypatch.setattr(
        "tradingagents_web.api.chat._has_inflight_turn",
        lambda db, aid: False,
    )
    r1 = auth_client.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "1"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r1.status_code == 201
    monkeypatch.setattr(
        "tradingagents_web.api.chat._has_inflight_turn",
        lambda db, aid: True,
    )
    r2 = auth_client.post(
        f"/api/runs/{a.run_id}/chat/turns",
        json={"text": "2"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 409
