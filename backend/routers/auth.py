"""Auth routes: register, login, and current-user."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from config import settings
from database import get_db
from limiter import limiter
from models import Player, User
from schemas import AuthConfig, Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# In the test environment we raise the cap so the test suite never hits the limit.
_TESTING = bool(os.environ.get("TESTING"))
_LOGIN_LIMIT = "1000/minute" if _TESTING else "10/minute"
_REGISTER_LIMIT = "1000/minute" if _TESTING else "5/minute"


@router.get("/config", response_model=AuthConfig)
def auth_config():
    """Public — tells the frontend whether an invite code is required to register."""
    return AuthConfig(invite_required=bool(settings.invite_code))


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit(_REGISTER_LIMIT)
def register(request: Request, body: UserCreate, db: Session = Depends(get_db)):
    if settings.invite_code and body.invite_code != settings.invite_code:
        raise HTTPException(status_code=403, detail="Invalid invite code")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.flush()  # get user.id

    # Link to an existing unregistered Player with the same name, or create a fresh one
    existing_player = db.query(Player).filter(Player.username == body.username).first()
    if existing_player:
        existing_player.user_id = user.id
    else:
        db.add(Player(username=body.username, user_id=user.id))

    db.commit()
    token = create_access_token({"sub": user.username})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
@limiter.limit(_LOGIN_LIMIT)
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    token = create_access_token({"sub": user.username})
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
