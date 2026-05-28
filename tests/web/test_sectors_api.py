"""Tests for /api/sectors CRUD endpoints."""

from datetime import datetime, timezone

# All mutating endpoints require the same CSRF marker every other API uses.
XHR_HEADERS = {"X-Requested-With": "fetch"}


def test_list_sectors_returns_presets(auth_client):
    # On a fresh sqlite from the test fixture there are no presets yet
    # (the fixture uses Base.metadata.create_all, not Alembic migrations).
    resp = auth_client.get("/api/sectors")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


def test_create_user_sector(auth_client):
    resp = auth_client.post(
        "/api/sectors",
        headers=XHR_HEADERS,
        json={
            "name": "양자 컴퓨팅",
            "description": "양자 컴퓨팅 산업",
            "keywords": ["IonQ", "qubits"],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "양자 컴퓨팅"
    assert body["slug"]  # auto-generated
    assert body["is_preset"] is False
    assert body["keywords"] == ["IonQ", "qubits"]


def test_create_duplicate_slug_conflicts(auth_client):
    payload = {"name": "Quantum"}
    r1 = auth_client.post("/api/sectors", headers=XHR_HEADERS, json=payload)
    assert r1.status_code == 201
    r2 = auth_client.post("/api/sectors", headers=XHR_HEADERS, json=payload)
    assert r2.status_code == 409


def test_create_then_list_includes_new_sector(auth_client):
    auth_client.post("/api/sectors", headers=XHR_HEADERS, json={"name": "Robotics"})
    listing = auth_client.get("/api/sectors").json()
    slugs = {s["slug"] for s in listing}
    assert "robotics" in slugs


def test_delete_user_sector(auth_client):
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "DropMe"}
    ).json()
    resp = auth_client.delete(
        f"/api/sectors/{created['id']}", headers=XHR_HEADERS
    )
    assert resp.status_code == 204
    listing = auth_client.get("/api/sectors").json()
    assert all(s["id"] != created["id"] for s in listing)


def test_delete_preset_returns_409(auth_client, app_with_test_db):
    # Inject a preset directly via the test SessionLocal.
    from tradingagents_web.models import Sector

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        preset = Sector(
            slug="ai", name="AI", keywords=[], is_preset=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(preset)
        db.commit()
        sector_id = preset.id
    finally:
        db.close()
    resp = auth_client.delete(
        f"/api/sectors/{sector_id}", headers=XHR_HEADERS
    )
    assert resp.status_code == 409


def test_create_without_xhr_header_is_csrf_rejected(auth_client):
    """Mutating endpoints must reject requests missing X-Requested-With."""
    resp = auth_client.post("/api/sectors", json={"name": "NoCsrf"})
    assert resp.status_code == 403


def test_delete_without_xhr_header_is_csrf_rejected(auth_client):
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "ProtectMe"}
    ).json()
    resp = auth_client.delete(f"/api/sectors/{created['id']}")
    assert resp.status_code == 403


def test_unauth_returns_401(client_unauth):
    resp = client_unauth.get("/api/sectors")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Task 15: start-run + SSE stream endpoints
# ---------------------------------------------------------------------------


def test_start_run_returns_202(auth_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "AI"}
    ).json()
    resp = auth_client.post(
        f"/api/sectors/{created['id']}/runs",
        headers=XHR_HEADERS, json={},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "running"
    assert body["sector_id"] == created["id"]
    assert len(body["id"]) >= 10  # uuid


def test_start_run_unknown_sector_returns_404(auth_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    resp = auth_client.post(
        "/api/sectors/99999/runs", headers=XHR_HEADERS, json={}
    )
    assert resp.status_code == 404


def test_concurrent_run_for_same_sector_returns_409(
    auth_client, monkeypatch, app_with_test_db
):
    """If a run is already 'running', a second POST must 409."""
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "X"}
    ).json()
    # Inject a running SectorRun row directly.
    from tradingagents_web.models import SectorRun
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(SectorRun(
            id="busy", sector_id=created["id"], status="running", phase="macro",
            started_at=datetime.now(timezone.utc),
        ))
        db.commit()
    finally:
        db.close()
    resp = auth_client.post(
        f"/api/sectors/{created['id']}/runs",
        headers=XHR_HEADERS, json={},
    )
    assert resp.status_code == 409


def test_start_run_csrf_rejected_without_xhr(auth_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "Y"}
    ).json()
    resp = auth_client.post(f"/api/sectors/{created['id']}/runs", json={})
    assert resp.status_code == 403


def test_start_run_returns_503_without_fake_runner(auth_client, monkeypatch):
    """Real LLM wiring is deferred — production POST must fail fast at 503.

    Without this guard the route would 202 and then silently crash in the
    background driver with NotImplementedError once a real runner tried to
    invoke an unwired LLM factory.
    """
    monkeypatch.delenv("WEB_FAKE_RUNNER", raising=False)
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "Z"}
    ).json()
    resp = auth_client.post(
        f"/api/sectors/{created['id']}/runs",
        headers=XHR_HEADERS, json={},
    )
    assert resp.status_code == 503
    assert "WEB_FAKE_RUNNER" in resp.json()["detail"]
