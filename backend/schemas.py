"""Pydantic schemas — request bodies and response shapes."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator

from models import GameStatus, GameVariant, RoundStatus


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    invite_code: str = ""

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("username must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("username must be 50 characters or fewer")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthConfig(BaseModel):
    invite_required: bool


class TokenData(BaseModel):
    username: str | None = None


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

class PlayerResponse(BaseModel):
    id: int
    username: str
    is_registered: bool

    @classmethod
    def from_player(cls, player) -> "PlayerResponse":
        return cls(id=player.id, username=player.username, is_registered=player.user_id is not None)


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

class GamePlayerResponse(BaseModel):
    seat_index: int
    username: str
    is_registered: bool
    player_id: int

    @classmethod
    def from_game_player(cls, gp) -> "GamePlayerResponse":
        return cls(
            seat_index=gp.seat_index,
            username=gp.player.username,
            is_registered=gp.player.user_id is not None,
            player_id=gp.player_id,
        )


class GameResponse(BaseModel):
    id: int
    code: str
    status: GameStatus
    variant: GameVariant
    game_master_id: int
    game_master_username: str
    initial_dealer_seat: int | None
    max_cards_override: int | None
    created_at: datetime
    players: list[GamePlayerResponse]

    model_config = {"from_attributes": True}

    @classmethod
    def from_game(cls, game) -> "GameResponse":
        return cls(
            id=game.id,
            code=game.code,
            status=game.status,
            variant=game.variant,
            game_master_id=game.game_master_id,
            game_master_username=game.game_master.username,
            initial_dealer_seat=game.initial_dealer_seat,
            max_cards_override=game.max_cards_override,
            created_at=game.created_at,
            players=[GamePlayerResponse.from_game_player(gp) for gp in game.players],
        )


class ReorderRequest(BaseModel):
    order: list[str]  # usernames in desired seat order


class DealerRequest(BaseModel):
    dealer_username: str


class MaxCardsRequest(BaseModel):
    max_cards: int | None  # None clears the override and restores the default


class SetVariantRequest(BaseModel):
    variant: GameVariant


class GmAddPlayerRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 1:
            raise ValueError("username cannot be empty")
        if len(v) > 50:
            raise ValueError("username must be 50 characters or fewer")
        return v


# ---------------------------------------------------------------------------
# Rounds & Bidding
# ---------------------------------------------------------------------------

class RoundCreate(BaseModel):
    cards_per_player: int

    @field_validator("cards_per_player")
    @classmethod
    def cards_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("cards_per_player must be at least 1")
        return v


class BidCreate(BaseModel):
    bid: int

    @field_validator("bid")
    @classmethod
    def bid_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("bid cannot be negative")
        return v


class GmBidCreate(BaseModel):
    username: str
    bid: int

    @field_validator("bid")
    @classmethod
    def bid_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("bid cannot be negative")
        return v


class BidResponse(BaseModel):
    username: str
    seat_index: int
    bid: int


class RoundResponse(BaseModel):
    id: int
    round_number: int
    cards_per_player: int
    first_player_seat: int
    dealer_seat: int
    status: RoundStatus
    bids: list[BidResponse]

    @classmethod
    def from_round(cls, round_) -> "RoundResponse":
        num_players = len(round_.game.players)
        dealer_seat = (round_.first_player_seat - 1 + num_players) % num_players
        seat_by_player_id = {gp.player_id: gp.seat_index for gp in round_.game.players}
        return cls(
            id=round_.id,
            round_number=round_.round_number,
            cards_per_player=round_.cards_per_player,
            first_player_seat=round_.first_player_seat,
            dealer_seat=dealer_seat,
            status=round_.status,
            bids=[
                BidResponse(
                    username=b.player.username,
                    seat_index=seat_by_player_id[b.player_id],
                    bid=b.bid,
                )
                for b in round_.bids
            ],
        )


# ---------------------------------------------------------------------------
# Round results & Scoring
# ---------------------------------------------------------------------------

class PlayerResultIn(BaseModel):
    username: str
    tricks_won: int

    @field_validator("tricks_won")
    @classmethod
    def tricks_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("tricks_won cannot be negative")
        return v


class ResultsSubmit(BaseModel):
    results: list[PlayerResultIn]


class TrickResultResponse(BaseModel):
    username: str
    seat_index: int
    bid: int
    tricks_won: int
    score: int


class RoundResultsResponse(BaseModel):
    round_number: int
    cards_per_player: int
    results: list[TrickResultResponse]


class ScoreEntry(BaseModel):
    username: str
    seat_index: int
    total_score: int
    rounds_played: int


class ScoreboardResponse(BaseModel):
    game_code: str
    status: GameStatus
    scores: list[ScoreEntry]
