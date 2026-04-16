from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class GameStatus(str, PyEnum):
    lobby = "lobby"
    active = "active"
    finished = "finished"
    abandoned = "abandoned"


class GameVariant(str, PyEnum):
    mogspar = "mogspar"
    pirat_bridge = "pirat_bridge"


class RoundStatus(str, PyEnum):
    bidding = "bidding"
    playing = "playing"
    finished = "finished"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    player: Mapped[Optional["Player"]] = relationship(back_populates="user", uselist=False)


class Player(Base):
    """Represents any player — registered (user_id set) or unregistered (user_id None)."""
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[Optional["User"]] = relationship(back_populates="player")
    game_players: Mapped[list["GamePlayer"]] = relationship(back_populates="player")
    bids: Mapped[list["Bid"]] = relationship(back_populates="player")
    trick_results: Mapped[list["TrickResult"]] = relationship(back_populates="player")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus), default=GameStatus.lobby, nullable=False)
    game_master_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    initial_dealer_seat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_cards_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant: Mapped[GameVariant] = mapped_column(Enum(GameVariant), default=GameVariant.mogspar, nullable=False)

    game_master: Mapped["User"] = relationship(foreign_keys=[game_master_id])
    players: Mapped[list["GamePlayer"]] = relationship(back_populates="game", order_by="GamePlayer.seat_index", cascade="all, delete-orphan")
    rounds: Mapped[list["Round"]] = relationship(back_populates="game", order_by="Round.round_number", cascade="all, delete-orphan")


class GamePlayer(Base):
    __tablename__ = "game_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    seat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_game_player"),
        UniqueConstraint("game_id", "seat_index", name="uq_game_seat"),
    )

    game: Mapped["Game"] = relationship(back_populates="players")
    player: Mapped["Player"] = relationship(back_populates="game_players")


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cards_per_player: Mapped[int] = mapped_column(Integer, nullable=False)
    first_player_seat: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RoundStatus] = mapped_column(Enum(RoundStatus), default=RoundStatus.bidding, nullable=False)

    __table_args__ = (
        UniqueConstraint("game_id", "round_number", name="uq_game_round"),
    )

    game: Mapped["Game"] = relationship(back_populates="rounds")
    bids: Mapped[list["Bid"]] = relationship(back_populates="round", cascade="all, delete-orphan")
    trick_results: Mapped[list["TrickResult"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    bid: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("round_id", "player_id", name="uq_round_bid"),
    )

    round: Mapped["Round"] = relationship(back_populates="bids")
    player: Mapped["Player"] = relationship(back_populates="bids")


class TrickResult(Base):
    __tablename__ = "trick_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    tricks_won: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("round_id", "player_id", name="uq_round_trick_result"),
    )

    round: Mapped["Round"] = relationship(back_populates="trick_results")
    player: Mapped["Player"] = relationship(back_populates="trick_results")
