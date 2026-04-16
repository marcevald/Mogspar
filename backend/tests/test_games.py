"""Phase 3 tests — Game management: create, join, view, and start."""

from conftest import client, register_and_login  # noqa: F401


def create_game(client, headers):
    return client.post("/games", headers=headers)


# ---------------------------------------------------------------------------
# Create game
# ---------------------------------------------------------------------------

def test_create_game_returns_201(client):
    headers = register_and_login(client)
    assert create_game(client, headers).status_code == 201


def test_create_game_response_shape(client):
    headers = register_and_login(client)
    body = create_game(client, headers).json()
    assert "id" in body
    assert "code" in body
    assert len(body["code"]) == 6
    assert body["status"] == "lobby"
    assert body["variant"] == "mogspar"
    assert len(body["players"]) == 1
    assert body["players"][0]["username"] == "alice"
    assert body["players"][0]["seat_index"] == 0


def test_create_game_requires_auth(client):
    assert client.post("/games").status_code == 401


def test_create_game_sets_creator_as_game_master(client):
    headers = register_and_login(client)
    me = client.get("/auth/me", headers=headers).json()
    assert create_game(client, headers).json()["game_master_id"] == me["id"]


# ---------------------------------------------------------------------------
# Get game
# ---------------------------------------------------------------------------

def test_get_game_returns_game(client):
    headers = register_and_login(client)
    code = create_game(client, headers).json()["code"]
    resp = client.get(f"/games/{code}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == code


def test_get_game_not_found(client):
    headers = register_and_login(client)
    assert client.get("/games/XXXXXX", headers=headers).status_code == 404


def test_get_game_requires_auth(client):
    headers = register_and_login(client)
    code = create_game(client, headers).json()["code"]
    assert client.get(f"/games/{code}").status_code == 401


# ---------------------------------------------------------------------------
# Join game
# ---------------------------------------------------------------------------

def test_join_game_adds_player(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code = create_game(client, alice).json()["code"]
    resp = client.post(f"/games/{code}/join", headers=bob)
    assert resp.status_code == 200
    usernames = {p["username"] for p in resp.json()["players"]}
    assert {"alice", "bob"} == usernames


def test_join_game_assigns_next_seat(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code = create_game(client, alice).json()["code"]
    resp = client.post(f"/games/{code}/join", headers=bob)
    bob_player = next(p for p in resp.json()["players"] if p["username"] == "bob")
    assert bob_player["seat_index"] == 1


def test_join_game_duplicate_rejected(client):
    headers = register_and_login(client)
    code = create_game(client, headers).json()["code"]
    resp = client.post(f"/games/{code}/join", headers=headers)
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


def test_join_game_not_found(client):
    headers = register_and_login(client)
    assert client.post("/games/XXXXXX/join", headers=headers).status_code == 404


def test_join_game_requires_auth(client):
    headers = register_and_login(client)
    code = create_game(client, headers).json()["code"]
    assert client.post(f"/games/{code}/join").status_code == 401


def test_join_started_game_rejected(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    carol = register_and_login(client, "carol", "carol@example.com")
    code = create_game(client, alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/join", headers=carol)
    assert resp.status_code == 400
    assert "started" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Start game
# ---------------------------------------------------------------------------

def test_start_game_transitions_to_active(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code = create_game(client, alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    resp = client.post(f"/games/{code}/start", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_start_game_requires_game_master(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code = create_game(client, alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    assert client.post(f"/games/{code}/start", headers=bob).status_code == 403


def test_start_game_needs_two_players(client):
    headers = register_and_login(client)
    code = create_game(client, headers).json()["code"]
    resp = client.post(f"/games/{code}/start", headers=headers)
    assert resp.status_code == 400
    assert "2" in resp.json()["detail"]


def test_start_game_already_started(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code = create_game(client, alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/start", headers=alice)
    assert resp.status_code == 400
    assert "not in lobby" in resp.json()["detail"].lower()
