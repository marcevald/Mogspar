"""Phase 2 tests — Auth: register, login, JWT, and current-user endpoint."""

from conftest import client, register_and_login  # noqa: F401

ALICE = {"username": "alice", "email": "alice@example.com", "password": "password123", "invite_code": "invite"}


def register(client, payload=None):
    return client.post("/auth/register", json=payload or ALICE)


def login(client, username="alice", password="password123"):
    return client.post("/auth/login", data={"username": username, "password": password})


def auth_header(client):
    register(client)
    token = login(client).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_returns_201(client):
    assert register(client).status_code == 201


def test_register_response_shape(client):
    body = register(client).json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_username(client):
    register(client)
    resp = register(client)
    assert resp.status_code == 400
    assert "username" in resp.json()["detail"].lower()


def test_register_duplicate_email(client):
    register(client)
    resp = register(client, {**ALICE, "username": "alice2"})
    assert resp.status_code == 400
    assert "email" in resp.json()["detail"].lower()


def test_register_short_username(client):
    assert register(client, {**ALICE, "username": "ab"}).status_code == 422


def test_register_short_password(client):
    assert register(client, {**ALICE, "password": "short"}).status_code == 422


def test_register_invalid_email(client):
    assert register(client, {**ALICE, "email": "not-an-email"}).status_code == 422


def test_register_wrong_invite_code(client):
    resp = register(client, {**ALICE, "invite_code": "wrong"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_returns_token(client):
    register(client)
    body = login(client).json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    register(client)
    assert login(client, password="wrongpassword").status_code == 401


def test_login_unknown_user(client):
    assert login(client, username="nobody").status_code == 401


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------

def test_me_returns_current_user(client):
    resp = client.get("/auth/me", headers=auth_header(client))
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_me_requires_auth(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_bad_token(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer totallyinvalid"}).status_code == 401
