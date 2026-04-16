# Møgspar — Project Memory

This file is the source of truth for Claude Code. All decisions made during
planning are recorded here. Read this before doing anything in this project.

---

## What is Møgspar?

A mobile-first web app for tracking tricks in the Danish card game Møgspar.
Players use their phones during a physical card game to record bids, tricks
won, and scores in real time.

---

## Tech stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Frontend   | React + Vite + Tailwind CSS         |
| Backend    | Python + FastAPI                    |
| Database   | SQLite (dev) → PostgreSQL (Pi)      |
| Real-time  | WebSockets (FastAPI built-in)       |
| Auth       | JWT tokens                          |
| Deployment | Docker Compose                      |

---

## Game rules (important for logic implementation)

- A standard deck of cards is used
- Cards dealt per player depends on player count (max possible per round)
- **Spades beat all other suits**
- A player must follow suit; if they cannot, they may play anything
- Highest card of the led suit wins, unless a spade is played
- Each player guesses (bids) how many tricks they will win before each round

### Round sequence
A full game goes from max cards DOWN to 1, then back UP to max.
Example with 4 players (max 13 cards):
```
13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
```
**26 rounds total** — the 1-card round appears TWICE consecutively in the middle.
The first player to bid rotates by one seat each round.

### Last bidder constraint
The last player to bid in each round CANNOT make a bid that would cause the
total bids to equal the number of cards dealt. This must be enforced in both
the UI and backend validation.

```
forbidden_bid = cards_per_player - sum(all_previous_bids_this_round)
```
If `forbidden_bid < 0`, there is no forbidden value.

### Scoring formula
```
score = (10 + bid)        if tricks_won == bid      # exact match
score = -(abs(bid - tricks_won))   if tricks_won != bid      # wrong
```

---

## Data model

```
User
├── id, username, email, password_hash, is_active, created_at

Game
├── id, code (e.g. MØG-47), status (lobby|active|finished)
├── game_master_id → User
├── created_at, finished_at

GamePlayer  (join table — who is in a game)
├── game_id → Game
├── user_id → User
├── seat_index  (determines bid/play order)
├── joined_at

Round
├── id, game_id → Game
├── round_number (1–26)
├── cards_per_player
├── first_player_seat (rotates each round)
├── status (bidding|playing|finished)

Bid
├── id, round_id → Round
├── user_id → User
├── bid (integer, validated against last-bidder constraint)
├── created_at

TrickResult
├── id, round_id → Round
├── user_id → User
├── tricks_won
├── score  (computed and stored, not derived at query time)
├── created_at
```

---

## App screens (all designed, mockups approved)

| Screen                      | Who sees it      | Notes                                        |
|-----------------------------|------------------|----------------------------------------------|
| Login / Register            | Everyone         | Tab toggle between the two forms             |
| Home                        | Logged-in users  | Active games, join by code, past games       |
| Create game                 | GM               | Sets up game, others join later              |
| Game lobby                  | GM + players     | Share code, player list, GM starts           |
| Bidding phase — GM view     | GM only          | Enters bids in seat order, last-bidder rule shown |
| Bidding phase — player view | Players          | Read-only, sees bids appear in real time     |
| Trick entry                 | GM only          | Accordion rows per player, +/- steppers      |
| Live scoreboard             | Everyone         | Rankings + full round breakdown table        |
| Statistics                  | Everyone         | All-time leaderboard, personal history       |

### UI decisions
- **Design**: Mobile-first, system default colour scheme (auto dark/light)
- **Fonts**: Lora (display/numbers) + DM Sans (body)
- **Colours**: Teal accent, amber for GM/warnings, red for errors
- **Bids**: Entered by GM one at a time, with large +/- stepper, pre-filled
  with `floor(remaining_tricks / remaining_bidders)`
- **Tricks**: Accordion — tap a player row to expand their stepper, one active
  at a time. Shows "Bid: X · Tricks: Y" when collapsed.
- **Joining**: Both by share link/game code AND from list of open games
- **Bids visibility**: Visible to all players in real time as GM enters them
- **In-game navigation**: Bottom nav with Round / Scores / Game info tabs

---

## Build phases

| Phase | Description                          | Status      |
|-------|--------------------------------------|-------------|
| 1     | Project skeleton                     | ✅ Complete |
| 2     | Auth (register, login, JWT)          | ✅ Complete |
| 3     | Game management (create, join, lobby)| ✅ Complete |
| 4     | Bidding phase                        | ✅ Complete |
| 5     | Round play and scoring               | ✅ Complete |
| 6     | Statistics                           | ✅ Complete |

---

## Non-negotiable rules for every phase

1. **Security first** — all inputs validated, no secrets hardcoded, JWT auth
   on all protected endpoints, rate limiting on auth endpoints
2. **Tests before moving on** — every phase must have passing automated tests
   before starting the next phase
3. **Run tests with**: `docker compose run --rm backend pytest -v`
4. **Never assume** — if something is unclear, ask before implementing
5. **Verify before proceeding** — after each phase, confirm tests pass and the
   feature works end to end before moving to the next phase

---

## Project structure

```
mogspar/
├── backend/
│   ├── main.py          # FastAPI entry point, CORS, startup
│   ├── config.py        # All settings from environment variables
│   ├── database.py      # SQLAlchemy session and Base
│   ├── models.py        # All DB tables
│   ├── requirements.txt
│   └── tests/
│       └── test_health.py   # Phase 1 tests (all passing)
├── frontend/
│   └── src/
│       ├── main.jsx     # React entry point
│       └── App.jsx      # Route skeleton
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Daily workflow

```bash
docker compose up           # start everything
docker compose down         # stop everything
docker compose up --build   # rebuild after requirements/package changes
docker compose run --rm backend pytest -v   # run tests
```

---

## Hosting target

Self-hosted on a Raspberry Pi at home. Docker Compose deployment.
SQLite for now, PostgreSQL migration planned for later.

### Mockup file
The full interactive mockup for all 9 screens is in `docs/mockups.html`.
Read this file to understand the exact HTML structure, component layout,
colour variables, and interaction patterns to replicate in the real frontend.