"""Lobby management tests: gm-add, remove, reorder, dealer, max-cards, variant, abandon/resume, delete."""

from conftest import client, register_and_login  # noqa: F401


def _lobby(client, *usernames):
    """Create a game with the given users in the lobby. First user is GM."""
    headers = [register_and_login(client, u, f"{u}@example.com") for u in usernames]
    code = client.post("/games", headers=headers[0]).json()["code"]
    for h in headers[1:]:
        client.post(f"/games/{code}/join", headers=h)
    return code, headers


# ---------------------------------------------------------------------------
# GM-add player
# ---------------------------------------------------------------------------

def test_gm_add_player_returns_200(client):
    code, (alice,) = _lobby(client, "alice")
    resp = client.post(f"/games/{code}/gm-add", json={"username": "guest1"}, headers=alice)
    assert resp.status_code == 200


def test_gm_add_player_appears_in_game(client):
    code, (alice,) = _lobby(client, "alice")
    body = client.post(f"/games/{code}/gm-add", json={"username": "guest1"}, headers=alice).json()
    usernames = {p["username"] for p in body["players"]}
    assert "guest1" in usernames


def test_gm_add_player_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    resp = client.post(f"/games/{code}/gm-add", json={"username": "guest1"}, headers=bob)
    assert resp.status_code == 403


def test_gm_add_player_duplicate_rejected(client):
    code, (alice,) = _lobby(client, "alice")
    client.post(f"/games/{code}/gm-add", json={"username": "guest1"}, headers=alice)
    resp = client.post(f"/games/{code}/gm-add", json={"username": "guest1"}, headers=alice)
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


def test_gm_add_player_blocked_after_start(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/gm-add", json={"username": "carol"}, headers=alice)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Remove player
# ---------------------------------------------------------------------------

def test_remove_player_returns_200(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    # get bob's player id from game
    players = client.get(f"/games/{code}", headers=alice).json()["players"]
    bob_id = next(p["player_id"] for p in players if p["username"] == "bob")
    resp = client.delete(f"/games/{code}/players/{bob_id}", headers=alice)
    assert resp.status_code == 200
    usernames = {p["username"] for p in resp.json()["players"]}
    assert "bob" not in usernames


def test_remove_player_compacts_seats(client):
    code, (alice, bob, carol) = _lobby(client, "alice", "bob", "carol")
    players = client.get(f"/games/{code}", headers=alice).json()["players"]
    bob_id = next(p["player_id"] for p in players if p["username"] == "bob")
    client.delete(f"/games/{code}/players/{bob_id}", headers=alice)
    seats = sorted(p["seat_index"] for p in client.get(f"/games/{code}", headers=alice).json()["players"])
    assert seats == list(range(len(seats)))


def test_remove_player_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    players = client.get(f"/games/{code}", headers=alice).json()["players"]
    alice_id = next(p["player_id"] for p in players if p["username"] == "alice")
    assert client.delete(f"/games/{code}/players/{alice_id}", headers=bob).status_code == 403


def test_remove_gm_rejected(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    players = client.get(f"/games/{code}", headers=alice).json()["players"]
    alice_id = next(p["player_id"] for p in players if p["username"] == "alice")
    resp = client.delete(f"/games/{code}/players/{alice_id}", headers=alice)
    assert resp.status_code == 400
    assert "game master" in resp.json()["detail"].lower()


def test_remove_player_not_found(client):
    code, (alice,) = _lobby(client, "alice")
    assert client.delete(f"/games/{code}/players/99999", headers=alice).status_code == 404


# ---------------------------------------------------------------------------
# Reorder players
# ---------------------------------------------------------------------------

def test_reorder_updates_seats(client):
    code, (alice, bob, carol) = _lobby(client, "alice", "bob", "carol")
    resp = client.post(f"/games/{code}/reorder",
                       json={"order": ["carol", "alice", "bob"]}, headers=alice)
    assert resp.status_code == 200
    players = {p["username"]: p for p in resp.json()["players"]}
    assert players["carol"]["seat_index"] == 0
    assert players["alice"]["seat_index"] == 1
    assert players["bob"]["seat_index"]   == 2


def test_reorder_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    assert client.post(f"/games/{code}/reorder",
                       json={"order": ["bob", "alice"]}, headers=bob).status_code == 403


def test_reorder_must_include_all_players(client):
    code, (alice, bob, carol) = _lobby(client, "alice", "bob", "carol")
    resp = client.post(f"/games/{code}/reorder",
                       json={"order": ["alice", "bob"]}, headers=alice)
    assert resp.status_code == 400
    assert "every player" in resp.json()["detail"].lower()


def test_reorder_blocked_after_start(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/reorder",
                       json={"order": ["bob", "alice"]}, headers=alice)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Set dealer
# ---------------------------------------------------------------------------

def test_set_dealer_updates_initial_dealer(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    resp = client.post(f"/games/{code}/dealer",
                       json={"dealer_username": "bob"}, headers=alice)
    assert resp.status_code == 200


def test_set_dealer_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    assert client.post(f"/games/{code}/dealer",
                       json={"dealer_username": "alice"}, headers=bob).status_code == 403


def test_set_dealer_unknown_player(client):
    code, (alice,) = _lobby(client, "alice")
    assert client.post(f"/games/{code}/dealer",
                       json={"dealer_username": "nobody"}, headers=alice).status_code == 404


# ---------------------------------------------------------------------------
# Set max cards
# ---------------------------------------------------------------------------

def test_set_max_cards_accepted(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    resp = client.post(f"/games/{code}/max-cards", json={"max_cards": 5}, headers=alice)
    assert resp.status_code == 200
    assert resp.json()["max_cards_override"] == 5


def test_set_max_cards_clear(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/max-cards", json={"max_cards": 5}, headers=alice)
    resp = client.post(f"/games/{code}/max-cards", json={"max_cards": None}, headers=alice)
    assert resp.json()["max_cards_override"] is None


def test_set_max_cards_exceeds_absolute_max(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    # 2 players → absolute max is 52//2 = 26
    resp = client.post(f"/games/{code}/max-cards", json={"max_cards": 27}, headers=alice)
    assert resp.status_code == 400


def test_set_max_cards_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    assert client.post(f"/games/{code}/max-cards",
                       json={"max_cards": 5}, headers=bob).status_code == 403


# ---------------------------------------------------------------------------
# Set variant
# ---------------------------------------------------------------------------

def test_set_variant_accepted(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    resp = client.post(f"/games/{code}/variant",
                       json={"variant": "pirat_bridge"}, headers=alice)
    assert resp.status_code == 200
    assert resp.json()["variant"] == "pirat_bridge"


def test_set_variant_back_to_mogspar(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/variant", json={"variant": "pirat_bridge"}, headers=alice)
    resp = client.post(f"/games/{code}/variant", json={"variant": "mogspar"}, headers=alice)
    assert resp.json()["variant"] == "mogspar"


def test_set_variant_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    assert client.post(f"/games/{code}/variant",
                       json={"variant": "pirat_bridge"}, headers=bob).status_code == 403


def test_set_variant_blocked_after_start(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/variant",
                       json={"variant": "pirat_bridge"}, headers=alice)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Abandon / resume
# ---------------------------------------------------------------------------

def test_abandon_game(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    resp = client.post(f"/games/{code}/abandon", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Game abandoned"


def test_abandon_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    assert client.post(f"/games/{code}/abandon", headers=bob).status_code == 403


def test_abandon_requires_active_game(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    # game is in lobby, not active
    assert client.post(f"/games/{code}/abandon", headers=alice).status_code == 400


def test_resume_game(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    client.post(f"/games/{code}/abandon", headers=alice)
    resp = client.post(f"/games/{code}/resume", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_resume_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    client.post(f"/games/{code}/abandon", headers=alice)
    assert client.post(f"/games/{code}/resume", headers=bob).status_code == 403


def test_resume_requires_abandoned_game(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    # game is active, not abandoned
    assert client.post(f"/games/{code}/resume", headers=alice).status_code == 400


# ---------------------------------------------------------------------------
# Delete game
# ---------------------------------------------------------------------------

def test_delete_game_returns_detail(client):
    code, (alice,) = _lobby(client, "alice")
    resp = client.delete(f"/games/{code}", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Game deleted"


def test_delete_game_actually_removes_it(client):
    code, (alice,) = _lobby(client, "alice")
    client.delete(f"/games/{code}", headers=alice)
    assert client.get(f"/games/{code}", headers=alice).status_code == 404


def test_delete_game_requires_game_master(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    assert client.delete(f"/games/{code}", headers=bob).status_code == 403


def test_delete_active_game_allowed(client):
    code, (alice, bob) = _lobby(client, "alice", "bob")
    client.post(f"/games/{code}/start", headers=alice)
    assert client.delete(f"/games/{code}", headers=alice).status_code == 200
