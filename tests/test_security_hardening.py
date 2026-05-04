import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

API_KEY = "test-api-key-12345"
ALLOWED_IP = "10.0.0.1"
BLOCKED_IP = "203.0.113.5"


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01"
        b"\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT"
        b"x\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("ALLOWED_IPS", ALLOWED_IP)
    monkeypatch.setenv("DEMO_MODE", "false")

    test_db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{test_db_path}")
    monkeypatch.setenv("IMAGES_DIR", str(tmp_path / "images"))

    from app.db import Base
    from app import main

    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(main, "IMAGES_DIR", tmp_path / "images")
    main.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    main.app.dependency_overrides[main.get_db] = override_get_db

    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


def _auth_headers(client_ip: str | None = None) -> dict[str, str]:
    headers = {"X-API-Key": API_KEY}
    if client_ip is not None:
        headers["X-Forwarded-For"] = client_ip
    return headers


def test_mutating_routes_block_non_allowed_ip(app_client):
    event_payload = {
        "source": "security-test",
        "payload": {"stid": "S-1", "exnum": "EX-1", "table": {"rows": []}},
    }

    event_response = app_client.post(
        "/v1/events",
        json=event_payload,
        headers=_auth_headers(BLOCKED_IP),
    )
    assert event_response.status_code == 403

    upload_response = app_client.post(
        "/v1/images",
        headers=_auth_headers(BLOCKED_IP),
        files={"file": ("blocked.png", _png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 403

    delete_response = app_client.delete(
        "/v1/images/1",
        headers=_auth_headers(BLOCKED_IP),
    )
    assert delete_response.status_code == 403


def test_mutating_routes_allow_allowed_ip(app_client):
    event_payload = {
        "source": "security-test",
        "payload": {"stid": "S-2", "exnum": "EX-2", "table": {"rows": []}},
    }

    event_response = app_client.post(
        "/v1/events",
        json=event_payload,
        headers=_auth_headers(ALLOWED_IP),
    )
    assert event_response.status_code == 200
    assert event_response.json()["payload"]["stid"] == "S-2"

    upload_response = app_client.post(
        "/v1/images",
        headers=_auth_headers(ALLOWED_IP),
        files={"file": ("allowed.png", _png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 201
    image_id = upload_response.json()["image_id"]

    delete_response = app_client.delete(
        f"/v1/images/{image_id}",
        headers=_auth_headers(ALLOWED_IP),
    )
    assert delete_response.status_code == 204


def test_upload_failure_rejects_non_image_file(app_client):
    response = app_client.post(
        "/v1/images",
        headers=_auth_headers(ALLOWED_IP),
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert "image" in response.json()["detail"].lower()


def test_public_image_get_success_and_404(app_client):
    upload_response = app_client.post(
        "/v1/images",
        headers=_auth_headers(ALLOWED_IP),
        files={"file": ("public.png", _png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 201
    image_id = upload_response.json()["image_id"]

    get_response = app_client.get(f"/v1/images/{image_id}")
    assert get_response.status_code == 200
    assert get_response.headers["content-type"] == "image/png"

    missing_response = app_client.get("/v1/images/999999")
    assert missing_response.status_code == 404


def test_read_only_routes_remain_public(app_client):
    health_response = app_client.get("/health")
    assert health_response.status_code == 200

    events_response = app_client.get("/v1/events", headers={"X-API-Key": API_KEY})
    assert events_response.status_code == 200
    assert events_response.json() == []


def test_demo_mode_bypasses_allowlist(app_client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    event_payload = {
        "source": "security-test",
        "payload": {"stid": "S-3", "exnum": "EX-3", "table": {"rows": []}},
    }

    event_response = app_client.post(
        "/v1/events",
        json=event_payload,
        headers=_auth_headers(BLOCKED_IP),
    )
    assert event_response.status_code == 200

    upload_response = app_client.post(
        "/v1/images",
        headers=_auth_headers(BLOCKED_IP),
        files={"file": ("demo.png", _png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 201


def test_delete_rejects_blocked_ip_even_for_existing_image(app_client):
    upload_response = app_client.post(
        "/v1/images",
        headers=_auth_headers(ALLOWED_IP),
        files={"file": ("delete-me.png", _png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 201
    image_id = upload_response.json()["image_id"]

    delete_response = app_client.delete(
        f"/v1/images/{image_id}",
        headers=_auth_headers(BLOCKED_IP),
    )
    assert delete_response.status_code == 403
