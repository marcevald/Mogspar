"""Round and bidding routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Bid, Game, GamePlayer, GameStatus, GameVariant, Round, RoundStatus, TrickResult, User
from schemas import (
    BidCreate,
    GmBidCreate,
    ResultsSubmit,
    RoundCreate,
    RoundResponse,
    RoundResultsResponse,
    ScoreboardResponse,
    ScoreEntry,
    TrickResultResponse,
)

router = APIRouter(prefix="/games", tags=["rounds"])


def _calculate_score(bid: int, tricks_won: int, variant: GameVariant = GameVariant.mogspar) -> int:
    """
    Møgspar:     hit = 10 + bid,          miss = -(|bid - tricks_won|)
    Pirat Bridge: hit = 10 + 2*tricks_won, miss = -2
    """
    if variant == GameVariant.pirat_bridge:
        return (10 + 2 * tricks_won) if bid == tricks_won else -2
    if bid == tricks_won:
        return 10 + bid
    return -abs(tricks_won - bid)


def _get_game(code: str, db: Session) -> Game:
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


def _get_active_game(code: str, db: Session) -> Game:
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != GameStatus.active:
        raise HTTPException(status_code=400, detail="Game is not active")
    return game


def _get_game_player(game: Game, user: User) -> GamePlayer:
    """Find the GamePlayer for the given user (via their linked Player record)."""
    gp = next((gp for gp in game.players if gp.player.user_id == user.id), None)
    if not gp:
        raise HTTPException(status_code=403, detail="You are not a player in this game")
    return gp


@router.post("/{code}/rounds", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
def create_round(
    code: str,
    body: RoundCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_active_game(code, db)

    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can create rounds")

    in_progress = any(r.status in (RoundStatus.bidding, RoundStatus.playing) for r in game.rounds)
    if in_progress:
        raise HTTPException(status_code=400, detail="A round is already in progress")

    num_players = len(game.players)
    round_number = len(game.rounds) + 1

    if game.initial_dealer_seat is None:
        game.initial_dealer_seat = num_players - 1

    first_player_seat = (game.initial_dealer_seat + round_number) % num_players

    max_cards = game.max_cards_override if game.max_cards_override is not None else 52 // num_players
    if body.cards_per_player > max_cards:
        raise HTTPException(
            status_code=400,
            detail=f"cards_per_player cannot exceed {max_cards} for {num_players} players",
        )

    round_ = Round(
        game_id=game.id,
        round_number=round_number,
        cards_per_player=body.cards_per_player,
        first_player_seat=first_player_seat,
    )
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return RoundResponse.from_round(round_)


@router.get("/{code}/rounds/{round_number}", response_model=RoundResponse)
def get_round(
    code: str,
    round_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_active_game(code, db)
    _get_game_player(game, current_user)

    round_ = (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == round_number)
        .first()
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return RoundResponse.from_round(round_)


@router.post("/{code}/rounds/{round_number}/bid", response_model=RoundResponse)
def place_bid(
    code: str,
    round_number: int,
    body: BidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_active_game(code, db)
    gp = _get_game_player(game, current_user)

    round_ = (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == round_number)
        .first()
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    if round_.status != RoundStatus.bidding:
        raise HTTPException(status_code=400, detail="Round is not in bidding phase")
    if body.bid > round_.cards_per_player:
        raise HTTPException(
            status_code=400,
            detail=f"Bid cannot exceed cards_per_player ({round_.cards_per_player})",
        )

    already_bid = (
        db.query(Bid).filter(Bid.round_id == round_.id, Bid.player_id == gp.player_id).first()
    )
    if already_bid:
        raise HTTPException(status_code=400, detail="You have already placed a bid this round")

    if len(round_.bids) == len(game.players) - 1:
        sum_so_far = sum(b.bid for b in round_.bids)
        forbidden = round_.cards_per_player - sum_so_far
        if forbidden >= 0 and body.bid == forbidden:
            raise HTTPException(
                status_code=400,
                detail=f"Forbidden bid: total bids cannot equal cards dealt",
            )

    db.add(Bid(round_id=round_.id, player_id=gp.player_id, bid=body.bid))
    db.flush()

    db.refresh(round_)
    if len(round_.bids) == len(game.players):
        round_.status = RoundStatus.playing

    db.commit()
    db.refresh(round_)
    return RoundResponse.from_round(round_)


@router.post("/{code}/rounds/{round_number}/gm-bid", response_model=RoundResponse)
def gm_place_bid(
    code: str,
    round_number: int,
    body: GmBidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Game master places a bid on behalf of any player."""
    game = _get_active_game(code, db)

    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can bid on behalf of players")

    round_ = (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == round_number)
        .first()
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    if round_.status != RoundStatus.bidding:
        raise HTTPException(status_code=400, detail="Round is not in bidding phase")
    if body.bid > round_.cards_per_player:
        raise HTTPException(
            status_code=400,
            detail=f"Bid cannot exceed cards_per_player ({round_.cards_per_player})",
        )

    gp = next((gp for gp in game.players if gp.player.username == body.username), None)
    if not gp:
        raise HTTPException(status_code=404, detail=f"Player '{body.username}' not found in this game")

    already_bid = (
        db.query(Bid).filter(Bid.round_id == round_.id, Bid.player_id == gp.player_id).first()
    )
    if already_bid:
        raise HTTPException(status_code=400, detail=f"{body.username} has already bid this round")

    if len(round_.bids) == len(game.players) - 1:
        sum_so_far = sum(b.bid for b in round_.bids)
        forbidden = round_.cards_per_player - sum_so_far
        if forbidden >= 0 and body.bid == forbidden:
            raise HTTPException(
                status_code=400,
                detail=f"Forbidden bid: total bids cannot equal cards dealt",
            )

    db.add(Bid(round_id=round_.id, player_id=gp.player_id, bid=body.bid))
    db.flush()

    db.refresh(round_)
    if len(round_.bids) == len(game.players):
        round_.status = RoundStatus.playing

    db.commit()
    db.refresh(round_)
    return RoundResponse.from_round(round_)


@router.post("/{code}/rounds/{round_number}/results", response_model=RoundResultsResponse)
def submit_results(
    code: str,
    round_number: int,
    body: ResultsSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_active_game(code, db)

    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can submit results")

    round_ = (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == round_number)
        .first()
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    if round_.status != RoundStatus.playing:
        raise HTTPException(status_code=400, detail="Round is not in playing phase")

    gp_by_name = {gp.player.username: gp for gp in game.players}
    submitted_names = [r.username for r in body.results]
    if sorted(submitted_names) != sorted(gp_by_name.keys()):
        raise HTTPException(status_code=400, detail="Results must include every player exactly once")

    total_tricks = sum(r.tricks_won for r in body.results)
    if total_tricks != round_.cards_per_player:
        raise HTTPException(
            status_code=400,
            detail=f"Total tricks won ({total_tricks}) must equal cards_per_player ({round_.cards_per_player})",
        )

    bid_by_player_id = {b.player_id: b.bid for b in round_.bids}
    response_rows: list[TrickResultResponse] = []

    for entry in body.results:
        gp = gp_by_name[entry.username]
        bid_value = bid_by_player_id[gp.player_id]
        score = _calculate_score(bid_value, entry.tricks_won, game.variant)

        db.add(TrickResult(
            round_id=round_.id,
            player_id=gp.player_id,
            tricks_won=entry.tricks_won,
            score=score,
        ))
        response_rows.append(TrickResultResponse(
            username=entry.username,
            seat_index=gp.seat_index,
            bid=bid_value,
            tricks_won=entry.tricks_won,
            score=score,
        ))

    round_.status = RoundStatus.finished
    db.commit()

    return RoundResultsResponse(
        round_number=round_.round_number,
        cards_per_player=round_.cards_per_player,
        results=sorted(response_rows, key=lambda r: r.seat_index),
    )


@router.get("/{code}/rounds/{round_number}/results", response_model=RoundResultsResponse)
def get_results(
    code: str,
    round_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_game(code, db)
    _get_game_player(game, current_user)

    round_ = (
        db.query(Round)
        .filter(Round.game_id == game.id, Round.round_number == round_number)
        .first()
    )
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    if round_.status != RoundStatus.finished:
        raise HTTPException(status_code=400, detail="Results not yet available")

    bid_by_player_id = {b.player_id: b.bid for b in round_.bids}
    gp_by_player_id = {gp.player_id: gp for gp in game.players}

    rows = [
        TrickResultResponse(
            username=tr.player.username,
            seat_index=gp_by_player_id[tr.player_id].seat_index,
            bid=bid_by_player_id[tr.player_id],
            tricks_won=tr.tricks_won,
            score=tr.score,
        )
        for tr in round_.trick_results
    ]
    return RoundResultsResponse(
        round_number=round_.round_number,
        cards_per_player=round_.cards_per_player,
        results=sorted(rows, key=lambda r: r.seat_index),
    )


@router.get("/{code}/score", response_model=ScoreboardResponse)
def get_scoreboard(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_game(code, db)
    _get_game_player(game, current_user)

    totals: dict[int, int] = {gp.player_id: 0 for gp in game.players}
    rounds_played: dict[int, int] = {gp.player_id: 0 for gp in game.players}

    for round_ in game.rounds:
        if round_.status == RoundStatus.finished:
            for tr in round_.trick_results:
                totals[tr.player_id] += tr.score
                rounds_played[tr.player_id] += 1

    gp_by_player_id = {gp.player_id: gp for gp in game.players}
    entries = [
        ScoreEntry(
            username=gp_by_player_id[pid].player.username,
            seat_index=gp_by_player_id[pid].seat_index,
            total_score=totals[pid],
            rounds_played=rounds_played[pid],
        )
        for pid in totals
    ]
    return ScoreboardResponse(
        game_code=game.code,
        status=game.status,
        scores=sorted(entries, key=lambda e: e.seat_index),
    )


@router.post("/{code}/finish", response_model=dict)
def finish_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = _get_active_game(code, db)

    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can finish the game")

    in_progress = any(r.status in (RoundStatus.bidding, RoundStatus.playing) for r in game.rounds)
    if in_progress:
        raise HTTPException(status_code=400, detail="Cannot finish game while a round is in progress")

    from datetime import datetime, timezone
    game.status = GameStatus.finished
    game.finished_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Game finished"}
