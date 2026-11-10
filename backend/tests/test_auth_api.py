import pytest

from app.auth import hash_password
from app.cli import create_household


def _bearer(resp):
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_public_create_endpoint_is_gone(client):
    resp = client.post("/api/auth/create", json={"name": "Home", "password": "secret"})
    assert resp.status_code in (404, 405)


def test_create_household_cli_helper(db_session):
    h = create_household(db_session, "  Home ", "secret")
    assert h.name == "Home"
    assert h.password_hash != "secret"


def test_create_rejects_empty_password(db_session):
    with pytest.raises(ValueError):
        create_household(db_session, "Home", "")


def test_create_rejects_blank_name(db_session):
    with pytest.raises(ValueError):
        create_household(db_session, "   ", "secret")


def test_create_duplicate_name_case_insensitive(db_session):
    create_household(db_session, "Home", "secret")
    with pytest.raises(ValueError):
        create_household(db_session, "home", "other")


def test_login(client, db_session):
    create_household(db_session, "Home", "secret")
    resp = client.post("/api/auth/login", json={"name": "  hOME ", "password": "secret"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client, db_session):
    create_household(db_session, "Home", "secret")
    resp = client.post("/api/auth/login", json={"name": "Home", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_name(client):
    resp = client.post("/api/auth/login", json={"name": "Nobody", "password": "secret"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid name or password"


def test_login_migrated_household_with_empty_password(client, household):
    resp = client.post("/api/auth/login", json={"name": household.name, "password": ""})
    assert resp.status_code == 200
    resp = client.post("/api/auth/login", json={"name": household.name, "password": "x"})
    assert resp.status_code == 401


def test_me_authenticated(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "AAAA-BBBB"
    assert "created_at" in data
    assert "password_hash" not in data


def test_me_unauthenticated(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_rename(client, auth_headers):
    resp = client.patch("/api/auth/me", json={"name": "Our flat"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Our flat"
    assert client.post("/api/auth/login", json={"name": "our flat", "password": ""}).status_code == 200


def test_rename_conflict(client, auth_headers, second_household):
    resp = client.patch("/api/auth/me", json={"name": "cccc-dddd"}, headers=auth_headers)
    assert resp.status_code == 409


def test_rename_case_only_change(client, auth_headers):
    resp = client.patch("/api/auth/me", json={"name": "aaaa-bbbb"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "aaaa-bbbb"


def test_change_password_from_empty(client, household, auth_headers):
    resp = client.patch(
        "/api/auth/me", json={"current_password": "", "new_password": "new"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert client.post("/api/auth/login", json={"name": household.name, "password": ""}).status_code == 401
    assert client.post("/api/auth/login", json={"name": household.name, "password": "new"}).status_code == 200


def test_change_password_wrong_current(client, household, db_session, auth_headers):
    household.password_hash = hash_password("old")
    db_session.commit()
    resp = client.patch(
        "/api/auth/me", json={"current_password": "nope", "new_password": "new"}, headers=auth_headers
    )
    assert resp.status_code == 403
    assert client.post("/api/auth/login", json={"name": household.name, "password": "old"}).status_code == 200


def test_change_password_rejects_empty(client, auth_headers):
    resp = client.patch(
        "/api/auth/me", json={"current_password": "", "new_password": ""}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_login_me_roundtrip(client, db_session):
    create_household(db_session, "Home", "secret")
    login_resp = client.post("/api/auth/login", json={"name": "Home", "password": "secret"})
    assert client.get("/api/auth/me", headers=_bearer(login_resp)).json()["name"] == "Home"
