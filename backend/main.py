from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import settings
from database import Base, engine
import models  # noqa: F401 — registers all ORM models with Base.metadata
from limiter import limiter
from routers import auth as auth_router, games as games_router, rounds as rounds_router
from routers import players as players_router, stats as stats_router

# Incremental column migrations (idempotent — silently ignored if column already exists)
_MIGRATIONS = [
    "ALTER TABLE games ADD COLUMN initial_dealer_seat INTEGER",
    "ALTER TABLE games ADD COLUMN max_cards_override INTEGER",
    "ALTER TABLE games ADD COLUMN variant TEXT NOT NULL DEFAULT 'mogspar'",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables and run incremental migrations on startup
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for sql in _MIGRATIONS:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
    yield


app = FastAPI(
    title="Møgspar API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router.router)
app.include_router(games_router.router)
app.include_router(rounds_router.router)
app.include_router(players_router.router)
app.include_router(stats_router.router)


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "version": "0.1.0"}
