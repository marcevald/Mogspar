"""Player search endpoint tests."""

from conftest import client, register_and_login  # noqa: F401


# ---------------------------------------------------------------------------
# GET /players
# ---------------------------------------------------------------------------

def test_search_players_returns_200(client):
    register_and_login(client, "alice", "alice@example.com")
    alice = register_and_login(client, "alice", "alice@example.com")
    assert client.get("/players", headers=alice).status_code == 200


def test_search_players_returns_list(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    # alice's Player record exists after creating a game
    client.post("/games", headers=alice)
    resp = client.get("/players", headers=alice)
    assert isinstance(resp.json(), list)


def test_search_players_by_prefix(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    register_and_login(client, "bob", "bob@example.com")
    # create games so Player records are created
    alice_headers = alice
    bob_headers   = register_and_login(client, "bob", "bob@example.com")
    client.post("/games", headers=alice_headers)
    client.post("/games", headers=bob_headers)

    resp = client.get("/players?q=ali", headers=alice_headers)
    usernames = [p["username"] for p in resp.json()]
    assert "alice" in usernames
    assert "bob" not in usernames


def test_search_players_empty_query_returns_all(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    client.post("/games", headers=alice)
    client.post("/games", headers=bob)

    resp = client.get("/players", headers=alice)
    usernames = {p["username"] for p in resp.json()}
    assert {"alice", "bob"} == usernames


def test_search_players_requires_auth(client):
    assert client.get("/players").status_code == 401


def test_search_players_includes_guest_players(client):
    """Players created via gm-add (no user account) also appear in search."""
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code  = client.post("/games", headers=alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/gm-add", json={"username": "guest_joe"}, headers=alice)

    resp = client.get("/players?q=guest", headers=alice)
    usernames = [p["username"] for p in resp.json()]
    assert "guest_joe" in usernames


def test_search_player_shape(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    client.post("/games", headers=alice)
    resp = client.get("/players?q=alice", headers=alice)
    assert len(resp.json()) > 0
    player = resp.json()[0]
    assert "username" in player
    assert "is_registered" in player
