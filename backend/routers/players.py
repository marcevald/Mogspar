"""Player search — registered and unregistered players."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Player, User
from schemas import PlayerResponse

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerResponse])
def search_players(
    q: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # auth required
):
    """Search all known players (registered and unregistered) by username prefix."""
    query = db.query(Player)
    if q:
        query = query.filter(Player.username.ilike(f"%{q}%"))
    players = query.order_by(Player.username).limit(20).all()
    return [PlayerResponse.from_player(p) for p in players]
