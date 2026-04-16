"""Phase 1 tests — API skeleton health checks."""

from sqlalchemy import inspect
from conftest import client  # noqa: F401 — pytest fixture


def test_health_returns_200(client):
    assert client.get("/health").status_code == 200


def test_health_response_shape(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_is_public(client):
    assert client.get("/health", headers={}).status_code == 200


def test_database_tables_created(client):
    from database import engine
    tables = set(inspect(engine).get_table_names())
    expected = {"users", "games", "game_players", "rounds", "bids", "trick_results", "players"}
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_cors_header_present(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in resp.headers


def test_unknown_route_returns_404(client):
    assert client.get("/this-does-not-exist").status_code == 404
