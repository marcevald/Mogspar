"""
Shared test configuration: environment setup, fixtures, and helpers.
Must be loaded before any test module imports application code.
"""

import os

# Set test environment before any app imports so config picks them up.
os.environ["DATABASE_URL"] = "sqlite:///./test_mogspar.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["INVITE_CODE"] = "invite"
os.environ["TESTING"] = "1"   # disables strict rate-limit caps in auth router

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app
from database import engine

# Tables in deletion order (children before parents)
_TABLES = ("trick_results", "bids", "rounds", "game_players", "games", "players", "users")


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all rows between tests."""
    yield
    with engine.connect() as conn:
        for table in _TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()


@pytest.fixture(scope="session", autouse=True)
def remove_test_db():
    """Remove the SQLite test file after the full session."""
    yield
    if os.path.exists("./test_mogspar.db"):
        os.remove("./test_mogspar.db")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Shared helpers (plain functions, not fixtures)
# ---------------------------------------------------------------------------

def register_and_login(client, username="alice", email="alice@example.com"):
    """Register a user and return an Authorization header dict."""
    client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": "password123",
        "invite_code": "invite",
    })
    resp = client.post("/auth/login", data={"username": username, "password": "password123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_active_game(client, *usernames):
    """
    Create a started 2-player game.
    First username is the GM (creator + starter); others join.
    Returns (game_code, [headers_for_each_player]).
    """
    headers = [register_and_login(client, u, f"{u}@example.com") for u in usernames]
    code = client.post("/games", headers=headers[0]).json()["code"]
    for h in headers[1:]:
        client.post(f"/games/{code}/join", headers=h)
    client.post(f"/games/{code}/start", headers=headers[0])
    return code, headers


def bid_round(client, code, round_number, alice_h, bob_h, alice_bid=1, bob_bid=1):
    """Have alice and bob place bids in round_number."""
    client.post(f"/games/{code}/rounds/{round_number}/bid", json={"bid": alice_bid}, headers=alice_h)
    client.post(f"/games/{code}/rounds/{round_number}/bid", json={"bid": bob_bid}, headers=bob_h)
