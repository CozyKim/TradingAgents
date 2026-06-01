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


def test_start_run_returns_503_with_unknown_llm_provider(auth_client, monkeypatch):
    """Misconfigured LLM provider must fail fast at 503 (probed eagerly).

    Without this guard the route would 202 and then crash in the background
    driver on first llm_factory() call, leaving the user no signal until
    they checked SectorRun.status.
    """
    monkeypatch.delenv("WEB_FAKE_RUNNER", raising=False)
    monkeypatch.setenv(
        "WEB_SECTOR_LLM_PROVIDER", "definitely-not-a-real-provider"
    )
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "Z"}
    ).json()
    resp = auth_client.post(
        f"/api/sectors/{created['id']}/runs",
        headers=XHR_HEADERS, json={},
    )
    assert resp.status_code == 503
    assert "provider" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Task 16: reports list + latest + single endpoints
# ---------------------------------------------------------------------------


def test_list_reports_empty_initially(auth_client):
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "Empty"}
    ).json()
    resp = auth_client.get(f"/api/sectors/{created['id']}/reports")
    assert resp.status_code == 200
    assert resp.json() == []


def test_latest_report_404_when_no_reports(auth_client):
    created = auth_client.post(
        "/api/sectors", headers=XHR_HEADERS, json={"name": "NoReports"}
    ).json()
    resp = auth_client.get(f"/api/sectors/{created['id']}/reports/latest")
    assert resp.status_code == 404


def test_reports_lifecycle(auth_client, app_with_test_db):
    """Insert 3 versions, then verify list ordering + latest + by-id retrieval."""
    from tradingagents_web.models import Sector, SectorReport, SectorRun

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sector = Sector(slug="testsec", name="Test", keywords=[], is_preset=False,
                        created_at=datetime.now(timezone.utc))
        db.add(sector)
        db.commit()
        sector_id = sector.id

        # Build 3 runs + 3 reports with versions 1, 2, 3
        report_ids: list[int] = []
        for v in (1, 2, 3):
            run = SectorRun(
                id=f"run-{v}", sector_id=sector_id, status="completed",
                phase="outlook",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            db.add(run)
            db.flush()
            report = SectorReport(
                sector_id=sector_id, run_id=run.id, version=v,
                report_md=f"v{v}", value_chain_mermaid="graph LR",
                companies=[], outlook_summary=f"summary v{v}",
                candidate_tickers=[],
                created_at=datetime.now(timezone.utc),
            )
            db.add(report)
            db.flush()
            report_ids.append(report.id)
        db.commit()
    finally:
        db.close()

    # List: 3 items, version desc
    listing = auth_client.get(f"/api/sectors/{sector_id}/reports").json()
    assert [r["version"] for r in listing] == [3, 2, 1]

    # Latest: version 3
    latest = auth_client.get(f"/api/sectors/{sector_id}/reports/latest").json()
    assert latest["version"] == 3
    assert latest["outlook_summary"] == "summary v3"
    assert latest["report_md"] == "v3"

    # By-id: middle one
    middle_id = report_ids[1]  # version 2
    by_id = auth_client.get(
        f"/api/sectors/{sector_id}/reports/{middle_id}"
    ).json()
    assert by_id["version"] == 2
    assert by_id["report_md"] == "v2"


def test_report_for_wrong_sector_returns_404(auth_client, app_with_test_db):
    """Report belongs to sector A; querying as sector B → 404 (no info leak)."""
    from tradingagents_web.models import Sector, SectorReport, SectorRun

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        s_a = Sector(slug="a", name="A", keywords=[],
                     created_at=datetime.now(timezone.utc))
        s_b = Sector(slug="b", name="B", keywords=[],
                     created_at=datetime.now(timezone.utc))
        db.add_all([s_a, s_b])
        db.commit()
        run = SectorRun(
            id="ra", sector_id=s_a.id, status="completed", phase="outlook",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()
        rep = SectorReport(
            sector_id=s_a.id, run_id="ra", version=1,
            report_md="", value_chain_mermaid="", companies=[],
            outlook_summary="", candidate_tickers=[],
            created_at=datetime.now(timezone.utc),
        )
        db.add(rep)
        db.commit()
        report_id = rep.id
        wrong_sector_id = s_b.id
    finally:
        db.close()
    resp = auth_client.get(
        f"/api/sectors/{wrong_sector_id}/reports/{report_id}"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Heartbeat pump
# ---------------------------------------------------------------------------
import asyncio

import pytest

from tradingagents_web.services.event_bus import EventBus


@pytest.mark.asyncio
async def test_heartbeat_pump_emits_until_stopped():
    from tradingagents_web.api.sectors import _heartbeat_pump

    bus = EventBus()
    stop = asyncio.Event()
    received: list[str] = []
    async with bus.subscribe("pump-run") as queue:
        pump = asyncio.create_task(
            _heartbeat_pump(bus, "pump-run", stop, interval=0.01)
        )
        for _ in range(2):
            ev = await asyncio.wait_for(queue.get(), 0.5)
            received.append(ev.type)
        stop.set()
        await pump
    assert received == ["heartbeat", "heartbeat"]
    assert bus.history("pump-run") == []  # buffer=False


def test_mark_orphan_runs_failed(app_with_test_db):
    from tradingagents_web.api.sectors import mark_orphan_runs_failed
    from tradingagents_web.models import Sector, SectorRun

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sector = Sector(
            slug="orphan", name="Orphan", keywords=[],
            created_at=datetime.now(timezone.utc),
        )
        db.add(sector)
        db.commit()
        sid = sector.id
        db.add(SectorRun(
            id="orphan-run", sector_id=sid, status="running",
            started_at=datetime.now(timezone.utc),
        ))
        db.add(SectorRun(
            id="done-run", sector_id=sid, status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        ))
        db.commit()
    finally:
        db.close()

    n = mark_orphan_runs_failed(TestSessionLocal)
    assert n == 1

    db = TestSessionLocal()
    try:
        orphan = db.get(SectorRun, "orphan-run")
        done = db.get(SectorRun, "done-run")
        assert orphan.status == "failed"
        assert "재시작" in (orphan.error or "")
        assert orphan.finished_at is not None
        assert done.status == "completed"  # 건드리지 않음
    finally:
        db.close()


def _make_running_run(TestSessionLocal, slug, run_id):
    from tradingagents_web.models import Sector, SectorRun
    db = TestSessionLocal()
    try:
        sector = Sector(
            slug=slug, name=slug, keywords=[],
            created_at=datetime.now(timezone.utc),
        )
        db.add(sector)
        db.commit()
        sid = sector.id
        db.add(SectorRun(
            id=run_id, sector_id=sid, status="running", phase="macro",
            started_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return sid
    finally:
        db.close()


def test_cancel_sector_run_marks_cancelled(auth_client, app_with_test_db):
    from tradingagents_web.models import SectorRun
    from tradingagents_web.services.event_bus import get_event_bus

    _, TestSessionLocal = app_with_test_db
    sid = _make_running_run(TestSessionLocal, "cancelme", "run-cancel")

    resp = auth_client.delete(
        f"/api/sectors/{sid}/runs/run-cancel", headers=XHR_HEADERS
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}

    db = TestSessionLocal()
    try:
        row = db.get(SectorRun, "run-cancel")
        assert row.status == "cancelled"
        assert row.finished_at is not None
    finally:
        db.close()

    types = [e.type for e in get_event_bus().history("run-cancel")]
    assert "cancelled" in types


def test_cancel_sector_run_wrong_sector_404(auth_client, app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    sid = _make_running_run(TestSessionLocal, "wrongsec", "run-wrong")
    # 존재하는 run이지만 다른 sector_id로 요청 → 404 (정보 노출 방지)
    resp = auth_client.delete(
        f"/api/sectors/{sid + 999}/runs/run-wrong", headers=XHR_HEADERS
    )
    assert resp.status_code == 404


def test_cancel_sector_run_not_running_409(auth_client, app_with_test_db):
    from tradingagents_web.models import Sector, SectorRun
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sector = Sector(
            slug="completed-sec", name="C", keywords=[],
            created_at=datetime.now(timezone.utc),
        )
        db.add(sector)
        db.commit()
        sid = sector.id
        db.add(SectorRun(
            id="run-done", sector_id=sid, status="completed",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        ))
        db.commit()
    finally:
        db.close()
    resp = auth_client.delete(
        f"/api/sectors/{sid}/runs/run-done", headers=XHR_HEADERS
    )
    assert resp.status_code == 409


def test_cancel_sector_run_csrf_rejected(auth_client, app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    sid = _make_running_run(TestSessionLocal, "csrfsec", "run-csrf")
    resp = auth_client.delete(f"/api/sectors/{sid}/runs/run-csrf")  # no XHR header
    assert resp.status_code == 403
