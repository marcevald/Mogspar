"""Statistics routes — leaderboard, personal stats, and scoped queries."""

from datetime import datetime
from enum import Enum
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Game, GameStatus, GameVariant, Player, Round, RoundStatus, TrickResult, User

router = APIRouter(prefix="/stats", tags=["stats"])


# ---------------------------------------------------------------------------
# Scope types
# ---------------------------------------------------------------------------

class Scope(str, Enum):
    all = "all"
    players = "players"
    game = "game"


class Match(str, Enum):
    exact = "exact"
    superset = "superset"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    username: str
    is_registered: bool
    games_played: int
    games_won: int
    total_score: int
    rounds_played: int
    bid_accuracy: float  # 0.0–1.0, -1 means no bids recorded


class RecentGame(BaseModel):
    code: str
    created_at: datetime
    status: GameStatus
    num_players: int
    rounds_played: int
    your_score: int
    rank: int  # your finishing position (1 = best)


class PersonalStats(BaseModel):
    username: str
    games_played: int
    games_won: int
    total_score: int
    rounds_played: int
    bid_accuracy: float
    recent_games: list[RecentGame]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_stats_for_games(games: list[Game]) -> dict:
    """
    Returns a dict keyed by player_id with aggregated stats across the given games.
    Only rounds with status=finished are counted.
    """
    stats: dict[int, dict] = {}

    for game in games:
        # Per-game score for win calculation
        game_score: dict[int, int] = {}

        for round_ in game.rounds:
            if round_.status != RoundStatus.finished:
                continue

            bid_by_player_id = {b.player_id: b for b in round_.bids}

            for tr in round_.trick_results:
                pid = tr.player_id
                if pid not in stats:
                    stats[pid] = {
                        "player": tr.player,
                        "game_ids": set(),
                        "games_won": 0,
                        "total_score": 0,
                        "rounds_played": 0,
                        "bids_hit": 0,
                        "bids_total": 0,
                    }
                stats[pid]["total_score"] += tr.score
                stats[pid]["rounds_played"] += 1
                stats[pid]["game_ids"].add(game.id)
                game_score[pid] = game_score.get(pid, 0) + tr.score

                b = bid_by_player_id.get(pid)
                if b:
                    stats[pid]["bids_total"] += 1
                    if b.bid == tr.tricks_won:
                        stats[pid]["bids_hit"] += 1

        # Determine winner(s) of this game
        if game_score:
            best = max(game_score.values())
            for pid, score in game_score.items():
                if score == best and pid in stats:
                    stats[pid]["games_won"] += 1

    return stats


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    variant: Optional[GameVariant] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """All-time leaderboard across all finished games, sorted by total score."""
    q = db.query(Game).filter(Game.status == GameStatus.finished)
    if variant is not None:
        q = q.filter(Game.variant == variant)
    finished_games = q.all()
    stats = _compute_stats_for_games(finished_games)

    entries = [
        LeaderboardEntry(
            username=s["player"].username,
            is_registered=s["player"].user_id is not None,
            games_played=len(s["game_ids"]),
            games_won=s["games_won"],
            total_score=s["total_score"],
            rounds_played=s["rounds_played"],
            bid_accuracy=round(s["bids_hit"] / s["bids_total"], 2) if s["bids_total"] else -1,
        )
        for s in stats.values()
    ]
    return sorted(entries, key=lambda e: e.total_score, reverse=True)


@router.get("/me", response_model=PersonalStats)
def get_my_stats(
    variant: Optional[GameVariant] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Personal stats and recent game history for the logged-in user."""
    player = db.query(Player).filter(Player.user_id == current_user.id).first()
    if not player:
        return PersonalStats(
            username=current_user.username,
            games_played=0, games_won=0, total_score=0,
            rounds_played=0, bid_accuracy=-1, recent_games=[],
        )

    # All games this player is part of, newest first
    game_ids = [gp.game_id for gp in player.game_players]
    q = db.query(Game).filter(Game.id.in_(game_ids))
    if variant is not None:
        q = q.filter(Game.variant == variant)
    all_games = q.order_by(Game.created_at.desc()).all()

    finished_games = [g for g in all_games if g.status == GameStatus.finished]
    stats = _compute_stats_for_games(finished_games)
    my = stats.get(player.id)

    recent_games: list[RecentGame] = []
    for game in all_games:
        # Compute all players' scores for this game
        game_score: dict[int, int] = {}
        rounds_counted = 0
        for round_ in game.rounds:
            if round_.status != RoundStatus.finished:
                continue
            rounds_counted += 1
            for tr in round_.trick_results:
                game_score[tr.player_id] = game_score.get(tr.player_id, 0) + tr.score

        my_score = game_score.get(player.id, 0)

        # Rank: how many players scored strictly higher than me?
        rank = 1 + sum(1 for s in game_score.values() if s > my_score)

        recent_games.append(RecentGame(
            code=game.code,
            created_at=game.created_at,
            status=game.status,
            num_players=len(game.players),
            rounds_played=rounds_counted,
            your_score=my_score,
            rank=rank,
        ))

    return PersonalStats(
        username=player.username,
        games_played=len(finished_games),
        games_won=my["games_won"] if my else 0,
        total_score=my["total_score"] if my else 0,
        rounds_played=my["rounds_played"] if my else 0,
        bid_accuracy=round(my["bids_hit"] / my["bids_total"], 2) if my and my["bids_total"] else -1,
        recent_games=recent_games,
    )


# ---------------------------------------------------------------------------
# Scoped stats + lineup discovery
# ---------------------------------------------------------------------------

class ScopedStatsResponse(BaseModel):
    scope: Scope
    match: Optional[Match] = None
    players_filter: Optional[list[str]] = None
    game_code: Optional[str] = None
    variant: Optional[GameVariant] = None
    games_count: int
    players: list[LeaderboardEntry]


class LineupInfo(BaseModel):
    players: list[str]      # sorted usernames
    games_count: int


def _usernames_of(game: Game) -> frozenset[str]:
    return frozenset(gp.player.username for gp in game.players)


def _filter_finished_games(
    db: Session,
    scope: Scope,
    *,
    variant: Optional[GameVariant] = None,
    players_filter: Optional[list[str]] = None,
    match: Optional[Match] = None,
    game_code: Optional[str] = None,
    current_user: Optional[User] = None,
) -> list[Game]:
    """
    Returns the list of finished games matching the given scope and filters.
    For scope=game the caller must be a player in the game (handled here).
    """
    q = db.query(Game).filter(Game.status == GameStatus.finished)
    if variant is not None:
        q = q.filter(Game.variant == variant)

    if scope == Scope.all:
        return q.all()

    if scope == Scope.players:
        if not players_filter:
            raise HTTPException(status_code=400, detail="'players' is required for scope=players")
        target = frozenset(players_filter)
        if match is None or match == Match.exact:
            return [g for g in q.all() if _usernames_of(g) == target]
        return [g for g in q.all() if target.issubset(_usernames_of(g))]

    # scope == Scope.game
    if not game_code:
        raise HTTPException(status_code=400, detail="'game_code' is required for scope=game")
    game = db.query(Game).filter(Game.code == game_code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != GameStatus.finished:
        raise HTTPException(status_code=400, detail="Game is not finished")
    if variant is not None and game.variant != variant:
        return []
    if current_user is not None:
        is_player = any(gp.player.user_id == current_user.id for gp in game.players)
        if not is_player:
            raise HTTPException(status_code=403, detail="You are not a player in this game")
    return [game]


@router.get("/scoped", response_model=ScopedStatsResponse)
def get_scoped_stats(
    scope: Scope = Query(...),
    match: Optional[Match] = Query(None),
    players: Optional[str] = Query(None, description="Comma-separated usernames"),
    game_code: Optional[str] = Query(None),
    variant: Optional[GameVariant] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified stats endpoint. Returns an aggregated leaderboard across the
    games matching the given scope. See the Scope enum for available modes.
    """
    players_list: Optional[list[str]] = None
    if players:
        players_list = [p.strip() for p in players.split(",") if p.strip()]
        if not players_list:
            raise HTTPException(status_code=400, detail="'players' cannot be empty")

    games = _filter_finished_games(
        db,
        scope,
        variant=variant,
        players_filter=players_list,
        match=match,
        game_code=game_code,
        current_user=current_user,
    )

    stats = _compute_stats_for_games(games)
    entries = [
        LeaderboardEntry(
            username=s["player"].username,
            is_registered=s["player"].user_id is not None,
            games_played=len(s["game_ids"]),
            games_won=s["games_won"],
            total_score=s["total_score"],
            rounds_played=s["rounds_played"],
            bid_accuracy=round(s["bids_hit"] / s["bids_total"], 2) if s["bids_total"] else -1,
        )
        for s in stats.values()
    ]
    return ScopedStatsResponse(
        scope=scope,
        match=match if scope == Scope.players else None,
        players_filter=players_list if scope == Scope.players else None,
        game_code=game_code if scope == Scope.game else None,
        variant=variant,
        games_count=len(games),
        players=sorted(entries, key=lambda e: e.total_score, reverse=True),
    )


@router.get("/lineups", response_model=list[LineupInfo])
def get_my_lineups(
    min_games: int = Query(2, ge=1, description="Minimum games for a lineup to surface"),
    variant: Optional[GameVariant] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recurring exact participant sets the current user has played with,
    sorted by games_count descending. A lineup only surfaces after at
    least min_games (default 2) occurrences.
    """
    player = db.query(Player).filter(Player.user_id == current_user.id).first()
    if not player:
        return []

    game_ids = [gp.game_id for gp in player.game_players]
    q = db.query(Game).filter(Game.id.in_(game_ids), Game.status == GameStatus.finished)
    if variant is not None:
        q = q.filter(Game.variant == variant)

    counts: dict[frozenset[str], int] = {}
    for g in q.all():
        key = _usernames_of(g)
        counts[key] = counts.get(key, 0) + 1

    lineups = [
        LineupInfo(players=sorted(list(k)), games_count=v)
        for k, v in counts.items()
        if v >= min_games
    ]
    return sorted(lineups, key=lambda l: (-l.games_count, l.players))
