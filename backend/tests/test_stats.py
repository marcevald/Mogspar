"""Statistics tests — leaderboard and personal stats endpoints."""

from conftest import client, register_and_login  # noqa: F401


def _finished_game(client, alice_bid=1, bob_bid=1):
    """
    Create a finished 2-player game with one scored round.
    cards=3, alice_bid=1, bob_bid=1 (2≠3 — safe with last-bidder constraint).
    alice wins 1 (hit, 11); bob wins 2 (miss, −1).
    Returns (code, alice_headers, bob_headers).
    """
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code  = client.post("/games", headers=alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/start", headers=alice)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": alice_bid}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": bob_bid}, headers=bob)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    client.post(f"/games/{code}/finish", headers=alice)
    return code, alice, bob


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def test_leaderboard_returns_200(client):
    _finished_game(client)
    alice = register_and_login(client, "alice", "alice@example.com")
    assert client.get("/stats/leaderboard", headers=alice).status_code == 200


def test_leaderboard_shape(client):
    _finished_game(client)
    alice = register_and_login(client, "alice", "alice@example.com")
    entries = client.get("/stats/leaderboard", headers=alice).json()
    assert isinstance(entries, list)
    entry = entries[0]
    for field in ("username", "is_registered", "games_played", "games_won",
                  "total_score", "rounds_played", "bid_accuracy"):
        assert field in entry


def test_leaderboard_sorted_by_score(client):
    _finished_game(client)
    alice = register_and_login(client, "alice", "alice@example.com")
    entries = client.get("/stats/leaderboard", headers=alice).json()
    scores = [e["total_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_leaderboard_contains_players(client):
    _finished_game(client)
    alice = register_and_login(client, "alice", "alice@example.com")
    entries = client.get("/stats/leaderboard", headers=alice).json()
    usernames = {e["username"] for e in entries}
    assert {"alice", "bob"} == usernames


def test_leaderboard_empty_before_any_games(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    entries = client.get("/stats/leaderboard", headers=alice).json()
    assert entries == []


def test_leaderboard_requires_auth(client):
    assert client.get("/stats/leaderboard").status_code == 401


def test_leaderboard_variant_filter(client):
    """Pirat Bridge games are excluded when filtering by mogspar."""
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code  = client.post("/games", headers=alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/variant", json={"variant": "pirat_bridge"}, headers=alice)
    client.post(f"/games/{code}/start", headers=alice)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=bob)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    client.post(f"/games/{code}/finish", headers=alice)

    # Filtering by mogspar should return no entries (only pirat_bridge game exists)
    entries = client.get("/stats/leaderboard?variant=mogspar", headers=alice).json()
    assert entries == []

    # Filtering by pirat_bridge should return the players
    entries_pb = client.get("/stats/leaderboard?variant=pirat_bridge", headers=alice).json()
    usernames = {e["username"] for e in entries_pb}
    assert {"alice", "bob"} == usernames


# ---------------------------------------------------------------------------
# Personal stats (/stats/me)
# ---------------------------------------------------------------------------

def test_me_returns_200(client):
    _, alice, _ = _finished_game(client)
    assert client.get("/stats/me", headers=alice).status_code == 200


def test_me_shape(client):
    _, alice, _ = _finished_game(client)
    body = client.get("/stats/me", headers=alice).json()
    for field in ("username", "games_played", "games_won", "total_score",
                  "rounds_played", "bid_accuracy", "recent_games"):
        assert field in body


def test_me_correct_stats(client):
    # alice hits (11), bob misses (-1). alice wins the game.
    _, alice, _ = _finished_game(client)
    body = client.get("/stats/me", headers=alice).json()
    assert body["username"] == "alice"
    assert body["games_played"] == 1
    assert body["games_won"] == 1
    assert body["total_score"] == 11
    assert body["rounds_played"] == 1
    assert body["bid_accuracy"] == 1.0   # 1 bid, hit


def test_me_recent_games_not_empty(client):
    _, alice, _ = _finished_game(client)
    body = client.get("/stats/me", headers=alice).json()
    assert len(body["recent_games"]) >= 1
    game = body["recent_games"][0]
    for field in ("code", "created_at", "status", "num_players",
                  "rounds_played", "your_score", "rank"):
        assert field in game


def test_me_no_games(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    body = client.get("/stats/me", headers=alice).json()
    assert body["games_played"] == 0
    assert body["total_score"] == 0
    assert body["recent_games"] == []


def test_me_requires_auth(client):
    assert client.get("/stats/me").status_code == 401


def test_me_variant_filter(client):
    """Personal stats variant filter only counts matching games."""
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")

    # Create one pirat_bridge finished game
    code = client.post("/games", headers=alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/variant", json={"variant": "pirat_bridge"}, headers=alice)
    client.post(f"/games/{code}/start", headers=alice)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=bob)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    client.post(f"/games/{code}/finish", headers=alice)

    body_mogspar = client.get("/stats/me?variant=mogspar", headers=alice).json()
    assert body_mogspar["games_played"] == 0

    body_pb = client.get("/stats/me?variant=pirat_bridge", headers=alice).json()
    assert body_pb["games_played"] == 1
