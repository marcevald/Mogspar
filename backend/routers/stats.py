"""Statistics routes — leaderboard and personal stats."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Game, GameStatus, GameVariant, Player, Round, RoundStatus, TrickResult, User

router = APIRouter(prefix="/stats", tags=["stats"])


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
