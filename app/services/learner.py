"""
Per-user stateful spending/savings learner.

Design goals (Phase 3/4):
  - Continuous LOCAL learning with NO heavy model retraining: every update is a
    single O(1) exponential-smoothing (Holt-Winters level) step, not a fit over
    the whole history. This keeps the free-tier CPU cost effectively constant
    regardless of how often the backend streams observations.
  - Strict multi-tenant isolation: all state is keyed exclusively by ``user_id``.
    No code path reads or blends another user's vector into an update or a
    prediction.
  - Same persistence architecture as content_tracker / visit_tracker: a per-user
    row in PostgreSQL (when DATABASE_URL is set) with an atomic JSON-file
    fallback, guarded by a process lock.

State per user:
    {
      "ewma_daily_spend":   float,   # smoothed variable spend per day
      "ewma_daily_savings": float,   # smoothed savings accrual per day
      "observations":       int,     # how many updates have folded in
      "updated":            ISO-8601 timestamp
    }
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# EWMA level-smoothing factor. Higher → recent observations dominate faster.
# 0.3 gives a stable trend that still adapts within a few updates.
_ALPHA = 0.3

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)
_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "learner_state.json")
_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─── DB backend ────────────────────────────────────────────────────────────────

def _ensure_table() -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_learner_state (
                    user_id INTEGER PRIMARY KEY,
                    data    JSONB   NOT NULL DEFAULT '{}'
                )
            """)
        conn.commit()


if _USE_DB:
    try:
        _ensure_table()
        logger.info("learner: using PostgreSQL for per-user state")
    except Exception as exc:  # pragma: no cover - infra-dependent
        logger.warning("learner: DB table setup failed (%s) — falling back to file", exc)
        _USE_DB = False


def _db_get(user_id: int) -> dict | None:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT data FROM ai_learner_state WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
    return dict(row["data"]) if row else None


def _db_upsert(user_id: int, data: dict) -> None:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_learner_state (user_id, data)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET data = EXCLUDED.data
                """,
                (user_id, psycopg2.extras.Json(data)),
            )
        conn.commit()


# ─── File backend ──────────────────────────────────────────────────────────────

def _file_load_all() -> dict:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save_all(data: dict) -> None:
    dir_path = os.path.dirname(_STATE_FILE)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ─── Unified single-user load / save (isolated by user_id) ──────────────────────

def _load(user_id: int) -> dict | None:
    if _USE_DB:
        return _db_get(user_id)
    return _file_load_all().get(str(user_id))


def _save(user_id: int, state: dict) -> None:
    if _USE_DB:
        _db_upsert(user_id, state)
    else:
        alld = _file_load_all()
        alld[str(user_id)] = state
        _file_save_all(alld)


# ─── Public API ──────────────────────────────────────────────────────────────

def record_observation(
    user_id: int,
    daily_spend: float,
    daily_savings: float = 0.0,
) -> dict:
    """
    Fold one observation into the user's profile with a single O(1) EWMA step.

    The first observation seeds the level directly; subsequent ones blend via
    ``_ALPHA``. Negative inputs are clamped to 0 (spend/savings rates are
    non-negative). Returns the updated state for this user only.
    """
    daily_spend = max(0.0, float(daily_spend))
    daily_savings = max(0.0, float(daily_savings))

    with _lock:
        prev = _load(user_id)
        if not prev or prev.get("observations", 0) <= 0:
            ewma_spend = daily_spend
            ewma_savings = daily_savings
            obs = 1
        else:
            ewma_spend = _ALPHA * daily_spend + (1 - _ALPHA) * float(prev["ewma_daily_spend"])
            ewma_savings = _ALPHA * daily_savings + (1 - _ALPHA) * float(prev["ewma_daily_savings"])
            obs = int(prev["observations"]) + 1

        state = {
            "ewma_daily_spend": round(ewma_spend, 4),
            "ewma_daily_savings": round(ewma_savings, 4),
            "observations": obs,
            "updated": _now_iso(),
        }
        _save(user_id, state)
        return state


def get_profile(user_id: int) -> dict | None:
    """Return the user's learner state, or None if they have none yet."""
    with _lock:
        return _load(user_id)


def predict(state: dict | None, days_remaining: int, current_savings_balance: float) -> dict:
    """
    Project from the smoothed rates. Pure function (no I/O), O(1).

    projected_spend            = ewma_daily_spend  × days_remaining
    projected_savings_balance  = current pool      + ewma_daily_savings × days_remaining
    """
    days = max(0, int(days_remaining))
    if not state:
        return {"projected_spend": 0.0, "projected_savings_balance": round(current_savings_balance, 2)}
    projected_spend = round(float(state["ewma_daily_spend"]) * days, 2)
    projected_savings = round(current_savings_balance + float(state["ewma_daily_savings"]) * days, 2)
    return {"projected_spend": projected_spend, "projected_savings_balance": projected_savings}
