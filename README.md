# ♠ Møgspar

A mobile-friendly web app for tracking tricks in the card game Møgspar.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | Python + FastAPI |
| Database | SQLite (dev) → PostgreSQL (production) |
| Real-time | WebSockets |
| Auth | JWT tokens |
| Deployment | Docker Compose |

---

## First-time setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd mogspar
```

### 2. Create your environment file
```bash
cp .env.example .env
```

Open `.env` in VS Code and replace `SECRET_KEY` with a real secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the output as the value of `SECRET_KEY` in `.env`.

### 3. Start the app
```bash
docker compose up --build
```

First run will take a few minutes while Docker downloads and builds images.
Subsequent starts are fast.

### 4. Open in your browser
| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

---

## Running the tests

Tests run inside Docker to match the production environment exactly:

```bash
docker compose run --rm backend pytest -v
```

You should see all tests passing before moving on to any new phase.

---

## Daily development workflow

```bash
# Start everything
docker compose up

# Stop everything
docker compose down

# Rebuild after changing requirements.txt or package.json
docker compose up --build

# Run tests
docker compose run --rm backend pytest -v

# View backend logs
docker compose logs backend

# View frontend logs
docker compose logs frontend
```

---

## Project structure

```
mogspar/
├── backend/
│   ├── main.py          # FastAPI entry point
│   ├── config.py        # All settings from environment variables
│   ├── database.py      # DB session and base model
│   ├── models.py        # All database tables
│   ├── requirements.txt
│   └── tests/
│       └── test_health.py
├── frontend/
│   └── src/
│       ├── main.jsx     # React entry point
│       └── App.jsx      # Route definitions
├── docker-compose.yml
├── .env.example         # Template — copy to .env and fill in
└── .gitignore
```

---

## Build phases

| Phase | Description | Status |
|---|---|---|
| 1 | Project skeleton | ✅ Done |
| 2 | Auth (register, login, JWT) | ✅ Done |
| 3 | Game management (create, join, lobby) | ✅ Done |
| 4 | Bidding phase | ✅ Done |
| 5 | Round play and scoring | ✅ Done |
| 6 | Statistics | ⬜ Next |
