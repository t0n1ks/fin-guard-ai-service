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

## ML & Analysis Pipeline

Each call to `POST /v1/analyze-behavior` runs five parallel computations — all deterministic, all in-process, no external ML service required:

| Component | Method | Output |
|---|---|---|
| **End-of-month forecast** | `scikit-learn` `LinearRegression` on cumulative daily expenses (≥7 data points) or simple daily average (< 7) | `predicted_end_of_month_balance: float` |
| **Financial health score** | Weighted composite of 4 normalised components: expense/income ratio (40%), goal adherence (30%), category diversity (20%), savings rate (10%) | `financial_health_score: int` (1–100) |
| **Sustainability score** | Case-insensitive keyword matching: "green" categories (transit, health, education, pharmacy) vs "negative" categories (fast food, gambling, alcohol) with a 1.5× penalty on negative | `sustainability_score: int` (1–100) |
| **Spending tier** | Rule-based classification: payday detection, weekly pace vs monthly limit, category diversity check | `spending_tier: str` (6 states) |
| **Multilingual nudge** | Template selection by tier + risk flags; variable substitution (rate, days left, top category); 99-char limit enforced | `smart_nudge: str` (EN/DE/RU/UA) |

The mood mapping (`thriving / content / worried / stressed / exhausted`) is derived from the composite health score after all five components are computed. The app's UFO no longer uses this mood: since Phase 2.21 the Go backend owns the companion's health and mood (from the cycle's real figures); the score still informs the nudge's risk flags.

---

## Features

### Financial Scoring
| Score | Range | Description |
|---|---|---|
| `financial_health_score` | 1–100 | Composite: spending pace + debt ratio + income stability |
| `sustainability_score` | 1–100 | Ratio of "green" (recurring, essential) vs. volatile spending |
| `predicted_end_of_month_balance` | float | Linear regression over daily expense totals; falls back to daily average with < 7 data points |

### Companion content pool (`app/data/pool/`)
All UFO wording lives in plain data files — never in database rows. Each bucket is an **append-only list** (an item's position is permanent; a removed item is marked `retired`). Items are **universal** (written once, translated into EN/DE/RU/UK) or **language-locked** (a pun that only works in one language is shown only to that language).

| Bucket | Where it appears | Daily cap |
|---|---|---|
| Jokes | the space cow | 2 |
| Facts | the shining star | 2 |
| Tips | an ambient UFO line | 1 |
| Exit lines | when a message is closed with ✕ | — |
| Quota lines | the cow / star once today's two are done | — |
| Encouragements | ambient fallback line | — |
| Message variants | the Go companion's contextual messages (incl. the weekly star/cow nudges) | Go's pacing |

**The daily caps reset at the user's local midnight.** Go resolves the user's timezone (the `X-User-Timezone` header, remembered on the profile, UTC fallback) and sends the user's local calendar date as `local_date` on `next-action`, `content` and `analyze-behavior`; this service never guesses a zone and uses the UTC date only when `local_date` is missing. The day only moves forward: after a timezone change to the west (local date earlier than the stored one) the stored day is kept, so a day's caps are never granted twice.

**No repeats:** a user is served items they haven't seen yet. When a bucket is exhausted, repeats may begin (never the last few shown), and the seen-set is reset only when the pass is at least **60 days** old — never while unseen items remain. Items added later are served first. Seen-state is shared across languages. The pool holds 180 universal jokes (+5 language-locked per language), 180 facts, 90 tips, 30 exit lines, 8 quota lines and 116 message variants (20 of them quest nudges) — with the caps, no repeated joke, fact or tip for ~90 days. Facts are accurate and evergreen; any calculation states its assumption and specific claims name their source.

**Safety:** tests scan every line in all four languages for shaming words and slurs.

### State persistence (compact, one user at a time)
- **`companion_seen`** — one binary row per user: a bitset per bucket, the day each pass began and the last few items / variants shown. About **200 bytes** of data (≈0.25 KB per user with row overhead) even at the full target pool size.
- **`tamagotchi_daily_state`** — one small row per user: today's date, how many jokes / facts / tips were served, the greeting flag and the pending advice. No item text.

Both live in the service's PostgreSQL (`DATABASE_URL`) with a JSON-file fallback for development; every read and write touches only the current user's row. Other rows: `visit_stats` (visit streak) and `ai_learner_state` (smoothed spending tracker). The app's companion health and mood are owned by the Go backend, not here.

- **ADVICE** — personalised nudge from `/analyze-behavior`, stored as pending
- **GREETING** — time-aware hello, once per day per user
- **TIP / ENCOURAGEMENT / RANDOM_ANIMATION** — the ambient channel (`next-action`), a tip at most once a day
- **Language routing** — `?language=uk` is normalised to `UA` internally; pool items use `en/de/ru/uk`

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

### `GET /v1/tamagotchi/content?user_id=42&category=joke&language=EN`

Category-locked content for **user-initiated** UFO entities (the Cow requests a `joke`, the Star a `fact`, a closed message an `exit` line) — distinct from the automatic `next-action` scheduler. `category` is one of `joke`, `fact`, `exit`, `advice`. Past the daily cap (2 jokes / 2 facts) the response is `type: "QUOTA"` with a short "more tomorrow" line.

**Auth:** `X-Brain-API-Key` header required.

**Response:** same shape as `next-action`; serves `{ "type": "NONE", "content": null }` when the requested category has no eligible content left for the day.
```json
{
  "type": "JOKE",
  "content": "I told my wallet a joke. It didn't laugh — it was a little short.",
  "animation_hint": "COW_ABDUCTION"
}
```

---

### `POST /v1/companion/render`

Words a companion message the Go backend has already chosen (Go decides what to say and when; this service only phrases it). Picks a variant from `app/data/pool/messages.py` for the type and language, fills in the numbers the way the language writes them (decimal comma for DE/RU/UK, the user's currency), never one of the last few variants the user saw for that type. Variants marked `calibrating` are used only while Go flags the first week of a period.

**Auth:** `X-Brain-API-Key` header required.

**Request body:**
```json
{ "user_id": 42, "type": "last_days", "tone": "supportive", "language": "ru",
  "currency": "EUR", "slots": { "remaining": 45.0, "days_left": 3, "daily": 15.0 } }
```

**Response:** `{ "text": "…" }`, or `{ "text": null }` when no variant fits — the app then uses its own four-language fallback.

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
| `GET /api/ai/next-action` | `GET /v1/tamagotchi/next-action` | Next UFO action (automatic scheduler) |
| `GET /api/ai/content` | `GET /v1/tamagotchi/content` | Category-locked content for user-triggered UFO entities |
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

**All rights reserved.** Copyright (c) 2026 Mykyta Titov (t0n1ks).

This project is **source-available for demonstration, portfolio, and review purposes only — it is not open source.** No permission is granted to use, copy, modify, distribute, sublicense, or sell any part of it without prior written permission from the author. See [LICENSE](LICENSE).
