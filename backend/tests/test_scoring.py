"""Phase 5 tests — Round play and scoring: submit results, scoreboard, finish game."""

from conftest import client, make_active_game, register_and_login  # noqa: F401


def _setup_playing_round(client, cards=3, alice_bid=1, bob_bid=1):
    """
    Create an active 2-player game, open round 1, and place bids.

    Note: in a 2-player game the last-bidder constraint prevents bids from
    summing to cards_per_player.  Defaults (1+1=2 with cards=3) are safe.
    Returns (code, alice_headers, bob_headers).
    """
    code, (alice, bob) = make_active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": cards}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": alice_bid}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": bob_bid}, headers=bob)
    return code, alice, bob


# ---------------------------------------------------------------------------
# Submit results
# ---------------------------------------------------------------------------

def test_submit_results_returns_200(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert resp.status_code == 200


def test_submit_results_response_shape(client):
    # cards=3, alice bids 1, bob bids 1 (2≠3 — allowed)
    # alice wins 1 → hit (11), bob wins 2 → miss (-1)
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=1, bob_bid=1)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    body = resp.json()
    assert body["round_number"] == 1
    assert body["cards_per_player"] == 3
    assert len(body["results"]) == 2

    alice_result = next(r for r in body["results"] if r["username"] == "alice")
    assert alice_result["bid"] == 1
    assert alice_result["tricks_won"] == 1
    assert alice_result["score"] == 11   # hit: 10 + 1

    bob_result = next(r for r in body["results"] if r["username"] == "bob")
    assert bob_result["bid"] == 1
    assert bob_result["tricks_won"] == 2
    assert bob_result["score"] == -1    # miss: -(|1-2|)


def test_scoring_miss(client):
    # alice bids 2, bob bids 0 (2≠3 — allowed; forbidden for bob = 3-2=1, bob bids 0≠1 → OK)
    # alice wins 1 → miss by 1 → -1; bob wins 2 → miss by 2 → -2
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=2, bob_bid=0)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    results = {r["username"]: r for r in resp.json()["results"]}
    assert results["alice"]["score"] == -1
    assert results["bob"]["score"] == -2


def test_scoring_bid_zero_hit(client):
    # alice bids 0, bob bids 2 (forbidden for bob = 3-0=3, bob bids 2≠3 → OK)
    # alice wins 0 → hit → 10; bob wins 3 → miss by 1 → -1
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=0, bob_bid=2)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 0},
            {"username": "bob",   "tricks_won": 3},
        ]
    })
    results = {r["username"]: r for r in resp.json()["results"]}
    assert results["alice"]["score"] == 10
    assert results["bob"]["score"] == -1   # miss: -(|2-3|)


def test_scoring_pirat_bridge(client):
    """Pirat Bridge: hit = 10 + 2*tricks_won, miss = -2."""
    alice = register_and_login(client, "alice", "alice@example.com")
    bob   = register_and_login(client, "bob",   "bob@example.com")
    code  = client.post("/games", headers=alice).json()["code"]
    client.post(f"/games/{code}/join", headers=bob)
    client.post(f"/games/{code}/variant", json={"variant": "pirat_bridge"}, headers=alice)
    client.post(f"/games/{code}/start", headers=alice)
    # cards=3, alice_bid=1, bob_bid=1 (2≠3 — allowed)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=bob)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},  # hit: 10 + 2*1 = 12
            {"username": "bob",   "tricks_won": 2},  # miss: -2
        ]
    })
    results = {r["username"]: r for r in resp.json()["results"]}
    assert results["alice"]["score"] == 12
    assert results["bob"]["score"]   == -2


def test_submit_results_requires_game_master(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=bob, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert resp.status_code == 403


def test_submit_results_wrong_total_tricks(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 2},
            {"username": "bob",   "tricks_won": 2},  # total 4 ≠ 3
        ]
    })
    assert resp.status_code == 400
    assert "cards_per_player" in resp.json()["detail"]


def test_submit_results_missing_player(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [{"username": "alice", "tricks_won": 3}]
    })
    assert resp.status_code == 400
    assert "every player" in resp.json()["detail"].lower()


def test_submit_results_unknown_player(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice",  "tricks_won": 1},
            {"username": "nobody", "tricks_won": 2},
        ]
    })
    assert resp.status_code == 400


def test_submit_results_duplicate_rejected(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    payload = {"results": [
        {"username": "alice", "tricks_won": 1},
        {"username": "bob",   "tricks_won": 2},
    ]}
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json=payload)
    assert client.post(f"/games/{code}/rounds/1/results", headers=alice, json=payload).status_code == 400


def test_submit_results_not_in_playing_phase(client):
    code, (alice, bob) = make_active_game(client, "alice", "bob")
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    # only alice has bid — round still in bidding phase
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    resp = client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert resp.status_code == 400
    assert "playing" in resp.json()["detail"].lower()


def test_submit_results_marks_round_finished(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert client.get(f"/games/{code}/rounds/1", headers=alice).json()["status"] == "finished"


# ---------------------------------------------------------------------------
# Get results
# ---------------------------------------------------------------------------

def test_get_results_returns_correct_data(client):
    # cards=3, alice_bid=1, bob_bid=1 (2≠3 — allowed)
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=1, bob_bid=1)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    resp = client.get(f"/games/{code}/rounds/1/results", headers=bob)
    assert resp.status_code == 200
    results = {r["username"]: r for r in resp.json()["results"]}
    assert results["alice"]["score"] == 11   # hit: 10+1
    assert results["bob"]["score"]   == -1   # miss: -(|1-2|)


def test_get_results_requires_player(client):
    eve = register_and_login(client, "eve", "eve@example.com")
    code, alice, bob = _setup_playing_round(client, cards=3)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert client.get(f"/games/{code}/rounds/1/results", headers=eve).status_code == 403


def test_get_results_not_yet_finished(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    resp = client.get(f"/games/{code}/rounds/1/results", headers=alice)
    assert resp.status_code == 400
    assert "not yet" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

def test_scoreboard_after_one_round(client):
    # cards=3, alice_bid=1, bob_bid=1: alice hits (11), bob misses (−1)
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=1, bob_bid=1)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    resp = client.get(f"/games/{code}/score", headers=alice)
    assert resp.status_code == 200
    scores = {s["username"]: s for s in resp.json()["scores"]}
    assert scores["alice"]["total_score"] == 11
    assert scores["bob"]["total_score"]   == -1
    assert scores["alice"]["rounds_played"] == 1


def test_scoreboard_accumulates_across_rounds(client):
    code, (alice, bob) = make_active_game(client, "alice", "bob")

    # Round 1: cards=3, alice_bid=1, bob_bid=1 (safe; 2≠3)
    # alice wins 1 → hit (11); bob wins 2 → miss (−1)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=alice)
    client.post(f"/games/{code}/rounds/1/bid", json={"bid": 1}, headers=bob)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })

    # Round 2: cards=3, alice_bid=2, bob_bid=0 (forbidden for bob=3−2=1, bids 0≠1 → OK)
    # alice wins 2 → hit (12); bob wins 1 → miss (−1)
    client.post(f"/games/{code}/rounds", json={"cards_per_player": 3}, headers=alice)
    client.post(f"/games/{code}/rounds/2/bid", json={"bid": 2}, headers=alice)
    client.post(f"/games/{code}/rounds/2/bid", json={"bid": 0}, headers=bob)
    client.post(f"/games/{code}/rounds/2/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 2},
            {"username": "bob",   "tricks_won": 1},
        ]
    })

    resp = client.get(f"/games/{code}/score", headers=alice)
    scores = {s["username"]: s for s in resp.json()["scores"]}
    assert scores["alice"]["total_score"] == 11 + 12   # 23
    assert scores["bob"]["total_score"]   == -1 + (-1)  # -2
    assert scores["alice"]["rounds_played"] == 2


def test_scoreboard_requires_player(client):
    eve = register_and_login(client, "eve", "eve@example.com")
    code, alice, bob = _setup_playing_round(client, cards=3)
    assert client.get(f"/games/{code}/score", headers=eve).status_code == 403


# ---------------------------------------------------------------------------
# Finish game
# ---------------------------------------------------------------------------

def test_finish_game(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    resp = client.post(f"/games/{code}/finish", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Game finished"


def test_finish_game_requires_game_master(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    assert client.post(f"/games/{code}/finish", headers=bob).status_code == 403


def test_finish_game_blocked_while_round_in_progress(client):
    code, alice, bob = _setup_playing_round(client, cards=3)
    # round 1 is still in playing phase
    resp = client.post(f"/games/{code}/finish", headers=alice)
    assert resp.status_code == 400
    assert "in progress" in resp.json()["detail"].lower()


def test_scoreboard_works_after_game_finished(client):
    code, alice, bob = _setup_playing_round(client, cards=3, alice_bid=1, bob_bid=1)
    client.post(f"/games/{code}/rounds/1/results", headers=alice, json={
        "results": [
            {"username": "alice", "tricks_won": 1},
            {"username": "bob",   "tricks_won": 2},
        ]
    })
    client.post(f"/games/{code}/finish", headers=alice)
    resp = client.get(f"/games/{code}/score", headers=bob)
    assert resp.status_code == 200
    assert resp.json()["status"] == "finished"
