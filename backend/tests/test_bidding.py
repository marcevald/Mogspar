"""Phase 4 tests — Bidding phase: create rounds, place bids, auto-transition."""

from conftest import client, register_and_login  # noqa: F401


def active_game(client, *players):
    """Create a started game with the given players. Returns (code, [headers...])."""
    headers = [register_and_login(client, p, f"{p}@example.com") for p in players]
    code = client.post("/games", headers=headers[0]).json()["code"]
    for h in headers[1:]:
        client.post(f"/games/{code}/join", headers=h)
    client.post(f"/games/{code}/start", headers=headers[0])
    return code, headers


# ---------------------------------------------------------------------------
# Create round
# ---------------------------------------------------------------------------

def test_create_round_returns_201(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    assert client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice).status_code == 201


def test_create_round_response_shape(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    body = client.post(f"/games/{code}/rounds", json={"cards_per_player": 4}, headers=alice).json()
    assert body["round_number"] == 1
    assert body["cards_per_player"] == 4
    assert body["status"] == "bidding"
    assert body["bids"] == []


def test_create_round_requires_game_master(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    assert client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=bob).status_code == 403


def test_create_round_requires_active_game(client):
    alice = register_and_login(client, "alice", "alice@example.com")
    code = client.post("/games", headers=alice).json()["code"]
    resp = client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert resp.status_code == 400
    assert "not active" in resp.json()["detail"].lower()


def test_create_round_blocks_while_in_progress(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert resp.status_code == 400
    assert "in progress" in resp.json()["detail"].lower()


def test_create_round_rotates_first_player_seat(client):
    code, (alice, bob, carol) = active_game(client, "alice", "bob", "carol")
    r1 = client.post(f"/games/{code}/rounds", json={"cards_per_player": 2}, headers=alice).json()
    assert r1["first_player_seat"] == 0


def test_cards_per_player_must_be_positive(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    assert client.post(f"/games/{code}/rounds", json={"cards_per_player": 0}, headers=alice).status_code == 422


def test_cards_per_player_max_for_player_count(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    resp = client.post(f"/games/{code}/rounds", json={"cards_per_player": 27}, headers=alice)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Get round
# ---------------------------------------------------------------------------

def test_get_round_returns_round(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.get(f"/games/{code}/rounds/1", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["round_number"] == 1


def test_get_round_not_found(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    assert client.get(f"/games/{code}/rounds/99", headers=alice).status_code == 404


def test_get_round_requires_player(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    outsider = register_and_login(client, "eve", "eve@example.com")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert client.get(f"/games/{code}/rounds/1", headers=outsider).status_code == 403


# ---------------------------------------------------------------------------
# Place bid (self-service)
# ---------------------------------------------------------------------------

def test_place_bid_accepted(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 2}, headers=alice)
    assert resp.status_code == 200
    bids = resp.json()["bids"]
    assert len(bids) == 1
    assert bids[0]["username"] == "alice"
    assert bids[0]["bid"] == 2


def test_bid_zero_accepted(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert client.post(f"/games/{code}/rounds/1/bid", json={"bid": 0}, headers=alice).status_code == 200


def test_bid_exceeds_cards_rejected(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 4}, headers=alice)
    assert resp.status_code == 400
    assert "cards_per_player" in resp.json()["detail"]


def test_bid_negative_rejected(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert client.post(f"/games/{code}/rounds/1/bid", json={"bid": -1}, headers=alice).status_code == 422


def test_duplicate_bid_rejected(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower()


def test_bid_requires_player(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    outsider = register_and_login(client, "eve", "eve@example.com")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=outsider).status_code == 403


# ---------------------------------------------------------------------------
# Auto-transition to playing
# ---------------------------------------------------------------------------

def test_all_bids_transitions_to_playing(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    # forbidden for bob = 3-1=2; bob bids 3 (≠2) → allowed
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 3}, headers=bob)
    assert resp.json()["status"] == "playing"
    assert len(resp.json()["bids"]) == 2


def test_partial_bids_stay_bidding(client):
    code, (alice, bob, carol) = active_game(client, "alice", "bob", "carol")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    assert client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice).json()["status"] == "bidding"


def test_cannot_bid_in_playing_phase(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 2}, headers=bob)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GM bid (on behalf of any player)
# ---------------------------------------------------------------------------

def test_gm_bid_accepted(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/gm-bid",
                       json={"username": "alice", "bid": 2}, headers=alice)
    assert resp.status_code == 200
    assert resp.json()["bids"][0]["bid"] == 2


def test_gm_bid_requires_game_master(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/gm-bid",
                       json={"username": "alice", "bid": 1}, headers=bob)
    assert resp.status_code == 403


def test_gm_bid_unknown_player_rejected(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/gm-bid",
                       json={"username": "nobody", "bid": 1}, headers=alice)
    assert resp.status_code == 404


def test_gm_bid_completes_round(client):
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/gm-bid", json={"username": "alice", "bid": 1}, headers=alice)
    # forbidden for bob = 3-1=2; bob bids 3 (≠2) → allowed
    resp = client.post(f"/games/{code}/rounds/1/gm-bid", json={"username": "bob", "bid": 3}, headers=alice)
    assert resp.json()["status"] == "playing"


# ---------------------------------------------------------------------------
# Last-bidder constraint
# ---------------------------------------------------------------------------

def test_last_bidder_forbidden_bid_rejected(client):
    """Last player cannot make total bids equal cards dealt."""
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    # alice bids 1; bob is last — forbidden bid = 3-1 = 2
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 2}, headers=bob)
    assert resp.status_code == 400
    assert "forbidden" in resp.json()["detail"].lower()


def test_last_bidder_allowed_when_sum_already_exceeds(client):
    """When previous bids already exceed cards, no bid is forbidden."""
    # Needs 3 players: alice and bob bid over cards, so carol's forbidden_bid < 0
    code, (alice, bob, carol) = active_game(client, "alice", "bob", "carol")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 2}, headers=alice)
    # alice bids 1, bob bids 2 (total=3 > 2); forbidden_bid for carol = 2-3 = -1 < 0 → no restriction
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 2}, headers=bob)
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 0}, headers=carol)
    assert resp.status_code == 200


def test_last_bidder_other_values_still_allowed(client):
    """Last bidder can bid a value that is not the forbidden one."""
    code, (alice, bob) = active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    # forbidden is 2, so 0, 1, or 3 are all allowed
    resp = client.post(f"/games/{code}/rounds/1/bid", json={"bid": 3}, headers=bob)
    assert resp.status_code == 200
