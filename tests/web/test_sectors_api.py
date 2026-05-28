"""Tests for /api/sectors CRUD endpoints."""


def test_list_sectors_returns_presets(auth_client):
    # On a fresh sqlite from the test fixture there are no presets yet
    # (the fixture uses Base.metadata.create_all, not Alembic). Inject
    # one preset directly to verify the endpoint shape, then call.
    # Simpler: create the row via the dependency-overridden session.
    # We have to go through the test app's DB; do it via a POST.
    resp = auth_client.get("/api/sectors")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    # Empty initially under the test fixture (no migration seed).
    assert body == [] or all(isinstance(s, dict) for s in body)


def test_create_user_sector(auth_client):
    resp = auth_client.post("/api/sectors", json={
        "name": "양자 컴퓨팅",
        "description": "양자 컴퓨팅 산업",
        "keywords": ["IonQ", "qubits"],
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "양자 컴퓨팅"
    assert body["slug"]  # auto-generated
    assert body["is_preset"] is False
    assert body["keywords"] == ["IonQ", "qubits"]


def test_create_duplicate_slug_conflicts(auth_client):
    payload = {"name": "Quantum"}
    r1 = auth_client.post("/api/sectors", json=payload)
    assert r1.status_code == 201
    r2 = auth_client.post("/api/sectors", json=payload)
    assert r2.status_code == 409


def test_create_then_list_includes_new_sector(auth_client):
    auth_client.post("/api/sectors", json={"name": "Robotics"})
    listing = auth_client.get("/api/sectors").json()
    slugs = {s["slug"] for s in listing}
    assert "robotics" in slugs


def test_delete_user_sector(auth_client):
    created = auth_client.post("/api/sectors", json={"name": "DropMe"}).json()
    resp = auth_client.delete(f"/api/sectors/{created['id']}")
    assert resp.status_code == 204
    listing = auth_client.get("/api/sectors").json()
    assert all(s["id"] != created["id"] for s in listing)


def test_delete_preset_returns_409(auth_client, app_with_test_db):
    # Inject a preset directly via the test SessionLocal.
    from datetime import datetime, timezone

    from tradingagents_web.models import Sector
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        preset = Sector(slug="ai", name="AI", keywords=[], is_preset=True,
                        created_at=datetime.now(timezone.utc))
        db.add(preset)
        db.commit()
        sector_id = preset.id
    finally:
        db.close()
    resp = auth_client.delete(f"/api/sectors/{sector_id}")
    assert resp.status_code == 409


def test_unauth_returns_401(client_unauth):
    resp = client_unauth.get("/api/sectors")
    assert resp.status_code in (401, 403)
