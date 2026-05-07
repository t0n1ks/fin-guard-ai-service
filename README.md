# FinGuard AI Brain

**A Python FastAPI microservice that acts as the intelligent companion for the [Financer](https://github.com/t0n1ks/go-react-angular-expense-tracker) expense tracker.**

It analyses spending behaviour, computes financial health scores, and drives the Tamagotchi UFO — serving time-aware greetings, jokes, financial facts, and personalised advice in four languages (EN / DE / RU / UK).

---

## Live Demo

The AI Brain is called automatically by the [Financer](https://go-react-angular-expense-tracker.vercel.app) frontend — no separate UI. You can hit the health endpoint directly:

```
GET https://your-brain.onrender.com/health
→ { "status": "ok" }
```

---

## Why a Separate Service?

The Go backend handles auth, data persistence, and the REST API. The Python service owns the heavy ML work (scikit-learn forecasting, statistical scoring) and all multilingual content — keeping two independently deployable, independently scalable units with a clean JSON API contract between them.

---

## Architecture

```
Browser / Vercel (React)
         │
         ▼
Go backend (Render)  ──── Neon PostgreSQL (users, transactions, categories)
         │
         │  POST /v1/analyze-behavior        (full profile + transactions)
         │  GET  /v1/tamagotchi/next-action  (user_id + language)
         │  POST /v1/tamagotchi/feedback     (accept / reject signal)
         ▼
FinGuard AI Brain (Render)  ──── Neon PostgreSQL (tamagotchi_daily_state)
```

All inter-service calls are authenticated with a shared `X-Brain-API-Key` header. The Go backend is the only allowed caller.

---

## Features

### Financial Scoring
| Score | Range | Description |
|---|---|---|
| `financial_health_score` | 1–100 | Composite: spending pace + debt ratio + income stability |
| `sustainability_score` | 1–100 | Ratio of "green" (recurring, essential) vs. volatile spending |
| `predicted_end_of_month_balance` | float | Linear regression over daily expense totals |

### Tamagotchi Content Engine
- **ADVICE** — AI-generated personalised nudge based on current spending tier and risk flags; stored as pending until the UFO is idle
- **GREETING** — time-aware hello (morning / afternoon / evening / night), shown once per day per user
- **JOKE** — up to 3 finance jokes per day, never repeated within a session (shuffle queue)
- **FACT** — up to 5 financial facts per day, with the same non-repeat guarantee
- **ENCOURAGEMENT** — positive reinforcement message when the daily content pool is exhausted
- **RANDOM_ANIMATION** — silent UFO event (cow abduction, coin shower, moon fly-by) as a final fallback
- **Apology mode** — after 2+ rejections in a day, messages are prefixed with a friendly retry phrase instead of being silenced
- **Language routing** — all content served in the language specified by the frontend query param (`?language=uk`); ISO 639-1 `uk` is normalised to internal code `UA` at every layer

### State Persistence
Per-user daily state (joke queue position, greeting flag, rejection count, pending advice) is stored in **Neon PostgreSQL** when `DATABASE_URL` is set, with automatic fallback to a local JSON file for development.

---

## API Reference

### `POST /v1/analyze-behavior`

Runs the full scoring pipeline and stores the generated nudge as pending advice.

**Auth:** `X-Brain-API-Key: <secret>` header required.

**Request body:**
```json
{
  "user_profile": {
    "user_id": 42,
    "currency": "USD",
    "monthly_spending_goal": 1500.0,
    "expected_salary": 3000.0,
    "payday_mode": "smart",
    "fixed_payday": 0,
    "manual_next_payday": null,
    "ai_humor_enabled": true,
    "language": "EN"
  },
  "transactions": [
    {
      "id": 1,
      "amount": 45.50,
      "category": { "id": 3, "name": "Food" },
      "date": "2026-05-07",
      "type": "expense",
      "income_type": "one_time",
      "description": "Lunch"
    }
  ],
  "analysis_date": "2026-05-07"
}
```

**Response:**
```json
{
  "financial_health_score": 74,
  "sustainability_score": 61,
  "predicted_end_of_month_balance": 842.30,
  "tamagotchi_mood": "content",
  "smart_nudge": "You're on track — 68% of your monthly budget used with 8 days left.",
  "spending_tier": "pacing_good",
  "risk_flags": []
}
```

---

### `GET /v1/tamagotchi/next-action?user_id=42&language=EN`

Returns the next action the Tamagotchi UFO should perform.

**Auth:** `X-Brain-API-Key` header required.

**Response:**
```json
{
  "type": "JOKE",
  "content": "Why did the piggy bank go to therapy? It had too many emotional deposits.",
  "animation_hint": "COW_ABDUCTION"
}
```

`type` is one of: `ADVICE`, `GREETING`, `JOKE`, `FACT`, `ENCOURAGEMENT`, `RANDOM_ANIMATION`.
`animation_hint` is one of: `COW_ABDUCTION`, `COIN_COLLECT`, `FLY_BY_MOON`.
`content` is `null` for `RANDOM_ANIMATION`.

---

### `POST /v1/tamagotchi/feedback`

Records whether the user accepted or dismissed the last message.
Two or more rejections in a day activate apology mode.

**Auth:** `X-Brain-API-Key` header required.

**Request body:**
```json
{ "user_id": 42, "accepted": false }
```

**Response:** `{ "status": "ok" }`

---

### `GET /health`

No auth required. Used by Render as a liveness probe.

**Response:** `{ "status": "ok" }`

---

## Getting Started Locally

### Prerequisites

- Python 3.12+
- (Optional) PostgreSQL or a [Neon](https://neon.tech) connection string

### Install & run

```bash
git clone https://github.com/t0n1ks/fin-guard-ai-service
cd fin-guard-ai-service

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set BRAIN_API_KEY to any string

uvicorn app.main:app --reload --port 8001
```

The service is now running at `http://localhost:8001`.

### Run with Docker

```bash
docker build -t fin-guard-ai-brain .
docker run -p 8001:8001 -e BRAIN_API_KEY=mysecret fin-guard-ai-brain
```

Or with docker-compose (also starts with proper healthcheck):

```bash
BRAIN_API_KEY=mysecret docker compose up --build
```

### Development dependencies

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BRAIN_API_KEY` | **Yes** | — | Shared secret; must match `AI_SERVICE_KEY` in the Go backend |
| `DATABASE_URL` | No | — | Neon/PostgreSQL connection string; falls back to local JSON file if unset |
| `PORT` | No | `8001` | Injected automatically by Render |
| `HOST` | No | `0.0.0.0` | Bind address |
| `LOG_LEVEL` | No | `info` | uvicorn log level (`debug`, `info`, `warning`, `error`) |

Generate a secure key:

```bash
openssl rand -hex 32
```

---

## Deployment on Render

1. Fork this repo to your GitHub account
2. In the [Render dashboard](https://render.com) → **New** → **Web Service** → connect your fork
3. Render will detect the included `render.yaml` and auto-configure the service
4. Set environment variables in the Render dashboard (never commit real values):
   - `BRAIN_API_KEY` — same value as `AI_SERVICE_KEY` on the Go backend
   - `DATABASE_URL` — your Neon connection string (same project as the Go backend; the service auto-creates its own `tamagotchi_daily_state` table on first boot)
5. Deploy. The service starts in ~30 s on Render's free tier

> Do **not** set `PORT` — Render injects it automatically via the environment.

---

## Integration with the Go Backend

The Go backend (`go-react-angular-expense-tracker`) calls this service via three routes in `backend/handlers/ai.go`:

| Go route | Proxied to | Purpose |
|---|---|---|
| `POST /api/ai/analyze` | `POST /v1/analyze-behavior` | Full spending analysis |
| `GET /api/ai/next-action` | `GET /v1/tamagotchi/next-action` | Next UFO action |
| `POST /api/ai/feedback` | `POST /v1/tamagotchi/feedback` | Accept / reject signal |

The Go backend gracefully degrades — all three endpoints return a safe empty response when this service is unreachable, so the UFO simply stays silent rather than crashing the frontend.

**Language normalisation chain:**
```
Frontend locale (i18next): "uk"
  → Go query param:         ?language=uk
  → Go normalizeLangForBrain: "ua"
  → Python endpoint:        lang.upper() → "UA", UK→UA mapping
  → content_tracker:        state stored with language="UA"
  → content served in Ukrainian
```

---

## Project Structure

```
fin-guard-ai-service/
├── app/
│   ├── main.py                        — FastAPI app, CORS middleware, router registration
│   ├── core/
│   │   └── config.py                  — Pydantic settings (BRAIN_API_KEY, PORT, LOG_LEVEL)
│   ├── api/v1/endpoints/
│   │   ├── analyze.py                 — POST /v1/analyze-behavior; verify_api_key dependency
│   │   └── tamagotchi.py              — GET /v1/tamagotchi/next-action; POST /v1/tamagotchi/feedback
│   ├── models/
│   │   ├── request.py                 — AnalyzeBehaviorRequest, UserProfile, TransactionItem
│   │   └── response.py                — AnalyzeBehaviorResponse, NextActionResponse
│   ├── services/
│   │   ├── health_scorer.py           — Composite financial health score (1–100)
│   │   ├── sustainability_scorer.py   — Green vs. volatile spending ratio (1–100)
│   │   ├── forecaster.py              — LinearRegression EOM balance prediction
│   │   ├── tier_calculator.py         — Weekly spending pace classification
│   │   ├── mood_engine.py             — Health score → Tamagotchi mood mapping
│   │   ├── nudge_generator.py         — Multilingual personalised advice generation
│   │   ├── content_tracker.py         — Per-user daily state (Neon PostgreSQL or JSON file)
│   │   └── tamagotchi_action.py       — Next-action orchestration (greeting/joke/fact/advice)
│   └── data/
│       ├── content.py                 — JOKES, FACTS, GREETINGS, ENCOURAGEMENTS (4 languages)
│       └── state/                     — Local JSON fallback (git-ignored)
├── Dockerfile                         — Python 3.12 multi-stage build
├── docker-compose.yml                 — Local dev with healthcheck
├── render.yaml                        — Render deployment configuration
├── requirements.txt                   — Production dependencies
├── requirements-dev.txt               — Test dependencies (pytest, httpx)
└── .env.example                       — Environment variable template
```

---

## Related Projects

| Repo | Description |
|---|---|
| [go-react-angular-expense-tracker](https://github.com/t0n1ks/go-react-angular-expense-tracker) | Go + React full-stack expense tracker; calls this service for all AI features |

---

## License

MIT
