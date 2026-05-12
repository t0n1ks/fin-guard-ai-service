from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import date as date_type

logger = logging.getLogger(__name__)

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)
_STATS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "visit_stats.json")
_lock = threading.Lock()


def _ensure_visit_table() -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tamagotchi_visit_stats (
                    user_id         INTEGER PRIMARY KEY,
                    last_visit_date TEXT    NOT NULL,
                    streak          INTEGER NOT NULL DEFAULT 1,
                    mood            TEXT    NOT NULL DEFAULT 'neutral'
                )
            """)
        conn.commit()


if _USE_DB:
    try:
        _ensure_visit_table()
        logger.info("visit_tracker: using Neon PostgreSQL")
    except Exception as exc:
        logger.warning("visit_tracker: DB table setup failed (%s) — falling back to file", exc)
        _USE_DB = False


# ─── File backend ─────────────────────────────────────────────────────────────

def _file_load() -> dict:
    try:
        with open(_STATS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save(data: dict) -> None:
    dir_path = os.path.dirname(_STATS_FILE)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _STATS_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ─── DB backend ───────────────────────────────────────────────────────────────

def _db_get(user_id: int) -> dict | None:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT last_visit_date, streak, mood FROM tamagotchi_visit_stats WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def _db_upsert(user_id: int, last_visit_date: str, streak: int, mood: str) -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tamagotchi_visit_stats (user_id, last_visit_date, streak, mood)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET last_visit_date = EXCLUDED.last_visit_date,
                        streak          = EXCLUDED.streak,
                        mood            = EXCLUDED.mood
                """,
                (user_id, last_visit_date, streak, mood),
            )
        conn.commit()


# ─── State computation ────────────────────────────────────────────────────────

def _compute_new_state(last_date_str: str, old_streak: int, today: str) -> tuple[str, int, str]:
    """Compute visit state for today, assuming last_date_str != today."""
    from datetime import date as dt
    gap = (dt.fromisoformat(today) - dt.fromisoformat(last_date_str)).days
    new_streak = old_streak + 1 if gap == 1 else 1
    if gap >= 3:
        mood = "grumpy"
    elif new_streak >= 3:
        mood = "cheerful"
    else:
        mood = "neutral"
    return today, new_streak, mood


# ─── Public API ───────────────────────────────────────────────────────────────

def record_visit(user_id: int) -> None:
    today = date_type.today().isoformat()
    with _lock:
        if _USE_DB:
            row = _db_get(user_id)
            if row is None:
                _db_upsert(user_id, today, 1, "neutral")
                return
            if row["last_visit_date"] == today:
                return
            new_date, new_streak, mood = _compute_new_state(
                row["last_visit_date"], row["streak"], today
            )
            _db_upsert(user_id, new_date, new_streak, mood)
        else:
            data = _file_load()
            key = str(user_id)
            row = data.get(key)
            if row is None:
                data[key] = {"last_visit_date": today, "streak": 1, "mood": "neutral"}
                _file_save(data)
                return
            if row["last_visit_date"] == today:
                return
            new_date, new_streak, mood = _compute_new_state(
                row["last_visit_date"], row["streak"], today
            )
            data[key] = {"last_visit_date": new_date, "streak": new_streak, "mood": mood}
            _file_save(data)


def get_visit_mood(user_id: int) -> str:
    with _lock:
        if _USE_DB:
            row = _db_get(user_id)
        else:
            data = _file_load()
            row = data.get(str(user_id))
    if row is None:
        return "neutral"
    return row.get("mood", "neutral")
