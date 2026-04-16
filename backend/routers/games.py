"""Game management routes: create, join, view, and start a game."""

import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Game, GamePlayer, GameStatus, Player, User
from schemas import (
    DealerRequest,
    GameResponse,
    GmAddPlayerRequest,
    MaxCardsRequest,
    ReorderRequest,
    SetVariantRequest,
)

router = APIRouter(prefix="/games", tags=["games"])

_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LENGTH = 6
_MIN_CARDS_PER_PLAYER = 2  # everyone must get at least this many cards at the game's peak round


def _generate_code(db: Session) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LENGTH))
        if not db.query(Game).filter(Game.code == code).first():
            return code
    raise RuntimeError("Failed to generate a unique game code")  # pragma: no cover


def _find_or_create_player(db: Session, user: User) -> Player:
    """Return the Player linked to this user, creating one if needed."""
    player = db.query(Player).filter(Player.user_id == user.id).first()
    if not player:
        player = Player(username=user.username, user_id=user.id)
        db.add(player)
        db.flush()
    return player


@router.get("", response_model=list[GameResponse])
def list_games(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all games the current user is a player in, newest first."""
    player = db.query(Player).filter(Player.user_id == current_user.id).first()
    if not player:
        return []
    game_ids = [gp.game_id for gp in player.game_players]
    games = (
        db.query(Game)
        .filter(Game.id.in_(game_ids))
        .order_by(Game.created_at.desc())
        .all()
    )
    return [GameResponse.from_game(g) for g in games]


@router.post("", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _generate_code(db)
    game = Game(code=code, game_master_id=current_user.id)
    db.add(game)
    db.flush()

    gm_player = _find_or_create_player(db, current_user)
    db.add(GamePlayer(game_id=game.id, player_id=gm_player.id, seat_index=0))
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.get("/{code}", response_model=GameResponse)
def get_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameResponse.from_game(game)


@router.post("/{code}/join", response_model=GameResponse)
def join_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Game has already started")

    player = _find_or_create_player(db, current_user)

    already_in = (
        db.query(GamePlayer)
        .filter(GamePlayer.game_id == game.id, GamePlayer.player_id == player.id)
        .first()
    )
    if already_in:
        raise HTTPException(status_code=400, detail="Already in this game")

    if 52 // (len(game.players) + 1) < _MIN_CARDS_PER_PLAYER:
        raise HTTPException(status_code=400, detail="Too many players — everyone must receive at least 2 cards")

    db.add(GamePlayer(game_id=game.id, player_id=player.id, seat_index=len(game.players)))
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/gm-add", response_model=GameResponse)
def gm_add_player(
    code: str,
    body: GmAddPlayerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM adds any player to the lobby by username — creating them if not yet known."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can add players")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot add players after the game has started")
    if 52 // (len(game.players) + 1) < _MIN_CARDS_PER_PLAYER:
        raise HTTPException(status_code=400, detail="Too many players — everyone must receive at least 2 cards")

    player = db.query(Player).filter(Player.username == body.username).first()
    if not player:
        player = Player(username=body.username)
        db.add(player)
        db.flush()

    already_in = (
        db.query(GamePlayer)
        .filter(GamePlayer.game_id == game.id, GamePlayer.player_id == player.id)
        .first()
    )
    if already_in:
        raise HTTPException(status_code=400, detail="Player is already in this game")

    db.add(GamePlayer(game_id=game.id, player_id=player.id, seat_index=len(game.players)))
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.delete("/{code}/players/{player_id}", response_model=GameResponse)
def gm_remove_player(
    code: str,
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM removes a player from the lobby."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can remove players")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot remove players after the game has started")

    gm_player = db.query(Player).filter(Player.user_id == current_user.id).first()
    if gm_player and gm_player.id == player_id:
        raise HTTPException(status_code=400, detail="Game master cannot remove themselves")

    gp = (
        db.query(GamePlayer)
        .filter(GamePlayer.game_id == game.id, GamePlayer.player_id == player_id)
        .first()
    )
    if not gp:
        raise HTTPException(status_code=404, detail="Player not in this game")

    removed_seat = gp.seat_index
    db.delete(gp)
    db.flush()

    # Re-compact seat indices
    for other_gp in game.players:
        if other_gp.seat_index > removed_seat:
            other_gp.seat_index -= 1

    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/reorder", response_model=GameResponse)
def reorder_players(
    code: str,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM sets the seat order before the game starts."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can reorder players")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot reorder after the game has started")

    gp_by_name = {gp.player.username: gp for gp in game.players}
    if sorted(body.order) != sorted(gp_by_name.keys()):
        raise HTTPException(status_code=400, detail="Order must include every player exactly once")

    # Phase 1: shift all seats to temporary high values to avoid unique-constraint
    # collisions during the reassignment (e.g. swapping seat 0 and 1).
    for gp in gp_by_name.values():
        gp.seat_index += 1000
    db.flush()

    # Phase 2: assign final seat indices
    for i, username in enumerate(body.order):
        gp_by_name[username].seat_index = i

    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/dealer", response_model=GameResponse)
def set_dealer(
    code: str,
    body: DealerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM sets the initial dealer before the game starts."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can set the dealer")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot change dealer after the game has started")

    gp = next((gp for gp in game.players if gp.player.username == body.dealer_username), None)
    if not gp:
        raise HTTPException(status_code=404, detail=f"Player '{body.dealer_username}' not found in this game")

    game.initial_dealer_seat = gp.seat_index
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/max-cards", response_model=GameResponse)
def set_max_cards(
    code: str,
    body: MaxCardsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM sets (or clears) the maximum cards-per-player override before the game starts."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can set the max cards")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot change max cards after the game has started")

    num_players = len(game.players)
    absolute_max = 52 // num_players

    if body.max_cards is not None:
        if body.max_cards < 1:
            raise HTTPException(status_code=400, detail="max_cards must be at least 1")
        if body.max_cards > absolute_max:
            raise HTTPException(
                status_code=400,
                detail=f"max_cards cannot exceed {absolute_max} for {num_players} players",
            )

    game.max_cards_override = body.max_cards
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/variant", response_model=GameResponse)
def set_variant(
    code: str,
    body: SetVariantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM sets the game variant before the game starts."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can set the variant")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Cannot change variant after the game has started")

    game.variant = body.variant
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.post("/{code}/abandon", response_model=dict)
def abandon_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM force-pauses an active game."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can abandon the game")
    if game.status != GameStatus.active:
        raise HTTPException(status_code=400, detail="Game is not active")

    game.status = GameStatus.abandoned
    db.commit()
    return {"detail": "Game abandoned"}


@router.post("/{code}/resume", response_model=GameResponse)
def resume_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GM resumes a previously abandoned game."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can resume the game")
    if game.status != GameStatus.abandoned:
        raise HTTPException(status_code=400, detail="Only abandoned games can be resumed")

    game.status = GameStatus.active
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


@router.delete("/{code}", response_model=dict)
def delete_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete a game and all its data. GM only."""
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can delete the game")

    db.delete(game)  # cascades to game_players, rounds → bids & trick_results
    db.commit()
    return {"detail": "Game deleted"}


@router.post("/{code}/start", response_model=GameResponse)
def start_game(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = db.query(Game).filter(Game.code == code).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.game_master_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game master can start the game")
    if game.status != GameStatus.lobby:
        raise HTTPException(status_code=400, detail="Game is not in lobby")
    if len(game.players) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 players to start")

    game.status = GameStatus.active
    db.commit()
    db.refresh(game)
    return GameResponse.from_game(game)


