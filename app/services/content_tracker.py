from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import threading
from datetime import date as date_type

from app.data.content import FACTS, JOKES

logger = logging.getLogger(__name__)

def _cap(text: str) -> str:
    return text if len(text) <= 99 else text[:99] + "…"

# ─── Storage backend ──────────────────────────────────────────────────────────

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)

_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "daily_state.json")
_lock = threading.Lock()


def _ensure_db_table() -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tamagotchi_daily_state (
                    user_id INTEGER PRIMARY KEY,
                    date    TEXT    NOT NULL,
                    data    JSONB   NOT NULL DEFAULT '{}'
                )
            """)
        conn.commit()


if _USE_DB:
    try:
        _ensure_db_table()
        logger.info("content_tracker: using Neon PostgreSQL for state persistence")
    except Exception as exc:
        logger.warning("content_tracker: DB table setup failed (%s) — falling back to file", exc)
        _USE_DB = False


# ─── File backend ─────────────────────────────────────────────────────────────

def _file_load_state() -> dict:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save_state(state: dict) -> None:
    dir_path = os.path.dirname(_STATE_FILE)
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ─── PostgreSQL backend ───────────────────────────────────────────────────────

def _db_load_state() -> dict:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id, data FROM tamagotchi_daily_state")
            rows = cur.fetchall()
    return {str(row["user_id"]): dict(row["data"]) for row in rows}


def _db_save_state(state: dict) -> None:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            for user_id_str, data in state.items():
                cur.execute(
                    """
                    INSERT INTO tamagotchi_daily_state (user_id, date, data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                        SET date = EXCLUDED.date,
                            data = EXCLUDED.data
                    """,
                    (int(user_id_str), data.get("date", ""), psycopg2.extras.Json(data)),
                )
        conn.commit()


# ─── Unified load / save ──────────────────────────────────────────────────────

def _load_state() -> dict:
    return _db_load_state() if _USE_DB else _file_load_state()


def _save_state(state: dict) -> None:
    if _USE_DB:
        _db_save_state(state)
    else:
        _file_save_state(state)


# ─── State helpers ────────────────────────────────────────────────────────────

def _ensure_user_state(state: dict, user_id: int, language: str, today: str) -> None:
    key = str(user_id)
    existing = state.get(key, {})
    same_day = existing.get("date") == today

    if same_day and existing.get("language") == language:
        return

    jokes = list(JOKES.get(language, JOKES["EN"]))
    facts = list(FACTS.get(language, FACTS["EN"]))
    random.shuffle(jokes)
    random.shuffle(facts)

    same_lang = existing.get("language") == language
    state[key] = {
        "date": today,
        "language": language,
        "joke_queue": jokes,
        "fact_queue": facts,
        "jokes_served": 0,
        "facts_served": 0,
        # Clear stale advice when language changes mid-day — was generated in wrong language
        "pending_advice": existing.get("pending_advice", "") if (same_day and same_lang) else "",
        "advice_consumed": existing.get("advice_consumed", True) if (same_day and same_lang) else True,
        "rejections_today": existing.get("rejections_today", 0) if same_day else 0,
        "greeting_served": existing.get("greeting_served", False) if same_day else False,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def get_next_joke(user_id: int, language: str) -> str | None:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if u["jokes_served"] >= 3:
            return None

        if not u["joke_queue"]:
            pool = list(JOKES.get(language, JOKES["EN"]))
            random.shuffle(pool)
            u["joke_queue"] = pool

        joke = u["joke_queue"].pop(0)
        u["jokes_served"] += 1
        _save_state(state)
        return _cap(joke)


def get_next_fact(user_id: int, language: str) -> str | None:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if u["facts_served"] >= 5:
            return None

        if not u["fact_queue"]:
            pool = list(FACTS.get(language, FACTS["EN"]))
            random.shuffle(pool)
            u["fact_queue"] = pool

        fact = u["fact_queue"].pop(0)
        u["facts_served"] += 1
        _save_state(state)
        return _cap(fact)


def get_pending_advice(user_id: int) -> str | None:
    with _lock:
        state = _load_state()
        key = str(user_id)
        u = state.get(key, {})

        if not u.get("pending_advice") or u.get("advice_consumed", True):
            return None

        advice = u["pending_advice"]
        u["advice_consumed"] = True
        state[key] = u
        _save_state(state)
        return advice


def store_pending_advice(user_id: int, advice: str) -> None:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        key = str(user_id)
        existing = state.get(key, {})

        if existing.get("date") == today:
            existing["pending_advice"] = advice
            existing["advice_consumed"] = False
            state[key] = existing
        else:
            state[key] = {
                "date": today,
                "language": existing.get("language", "EN"),
                "joke_queue": [],
                "fact_queue": [],
                "jokes_served": 0,
                "facts_served": 0,
                "pending_advice": advice,
                "advice_consumed": False,
                "rejections_today": 0,
                "greeting_served": False,
            }

        _save_state(state)


def record_rejection(user_id: int) -> None:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        key = str(user_id)
        existing = state.get(key, {})

        if existing.get("date") == today:
            existing["rejections_today"] = existing.get("rejections_today", 0) + 1
            state[key] = existing
        else:
            state[key] = {
                "date": today,
                "language": existing.get("language", "EN"),
                "joke_queue": [],
                "fact_queue": [],
                "jokes_served": 0,
                "facts_served": 0,
                "pending_advice": "",
                "advice_consumed": True,
                "rejections_today": 1,
                "greeting_served": False,
            }

        _save_state(state)


def is_apology_mode(user_id: int) -> bool:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        u = state.get(str(user_id), {})
        return u.get("date") == today and u.get("rejections_today", 0) >= 2


def get_greeting_served(user_id: int) -> bool:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        u = state.get(str(user_id), {})
        return u.get("date") == today and u.get("greeting_served", False)


def mark_greeting_served(user_id: int) -> None:
    with _lock:
        state = _load_state()
        key = str(user_id)
        u = state.get(key, {})
        u["greeting_served"] = True
        state[key] = u
        _save_state(state)
