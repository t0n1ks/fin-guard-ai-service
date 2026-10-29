"""
Per-user content serving for the UFO: jokes (the cow), facts (the star),
tips and encouragements (ambient lines), exit and quota lines, plus the small
daily flags (greeting served, pending advice).

Two kinds of per-user state, both touched one user at a time:

  * which pool items the user has seen — the compact bitset row in
    ``seen_store`` (~0.2–0.3 KB), never item text;
  * a tiny daily row (``tamagotchi_daily_state``): today's date and language,
    how many jokes / facts / tips were served today, the greeting flag and
    the pending advice. No item text, no queues.

Daily caps (jokes 2, facts 2, tips 1) make the pool sizes last: at the cap a
user meets no repeated joke or fact for ~90 days (see pool_picker.py).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from datetime import date as date_type
from typing import Optional

from app.data.pool import BUCKET_ITEMS
from app.data.pool.model import Item
from app.services import seen_store
from app.services.pool_picker import pick_item

logger = logging.getLogger(__name__)

# Maps the service's language codes to the pool's ISO codes.
_LANG_NORM: dict[str, str] = {"EN": "en", "DE": "de", "RU": "ru", "UA": "uk", "UK": "uk"}

DAILY_CAPS = {"jokes": 2, "facts": 2, "tips": 1}
_SERVED_KEY = {"jokes": "jokes_served", "facts": "facts_served", "tips": "tips_served"}
_ADVICE_MEMORY = 50  # hashes of recently served advice (dedup), not the texts

# Only these keys are stored; anything else in a legacy row is dropped on save.
_DAILY_KEYS = ("date", "language", "jokes_served", "facts_served", "tips_served",
               "greeting_served", "pending_advice", "advice_consumed", "seen_advice")
# Legacy (pre-pool) rows kept every seen text; they are imported once.
_LEGACY_SEEN = {"seen_jokes": "jokes", "seen_facts": "facts", "seen_budget_tips": "tips",
                "seen_encouragements": "encouragements"}

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "daily_state.json")
_lock = threading.Lock()


def iso(language: str) -> str:
    """Service language code (EN/DE/RU/UA) → pool code (en/de/ru/uk)."""
    return _LANG_NORM.get(language.upper(), language.lower() if language.lower() in ("en", "de", "ru", "uk") else "en")


def _cap(text: str) -> str:
    return text if len(text) <= 140 else text[:139] + "…"


# ─── Daily row: one user per read / write ──────────────────────────────────────

def _ensure_db_table() -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL, connect_timeout=5) as conn:
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
        logger.info("content_tracker: using PostgreSQL for state persistence")
    except Exception as exc:  # pragma: no cover - depends on the deployment
        logger.warning("content_tracker: DB table setup failed (%s) — falling back to file", exc)
        _USE_DB = False


def _db_load(user_id: int) -> dict:
    import psycopg2
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM tamagotchi_daily_state WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
    return dict(row[0]) if row else {}


def _db_save(user_id: int, data: dict) -> None:
    import psycopg2
    import psycopg2.extras
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tamagotchi_daily_state (user_id, date, data) VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET date = EXCLUDED.date, data = EXCLUDED.data
                """,
                (user_id, data.get("date", ""), psycopg2.extras.Json(data)),
            )
        conn.commit()


def _file_read() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _file_save(user_id: int, data: dict) -> None:
    all_rows = _file_read()
    all_rows[str(user_id)] = data
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def _load_user(user_id: int) -> dict:
    return _db_load(user_id) if _USE_DB else _file_read().get(str(user_id), {})


def _save_user(user_id: int, data: dict) -> None:
    slim = {k: data[k] for k in _DAILY_KEYS if k in data}
    if _USE_DB:
        _db_save(user_id, slim)
    else:
        _file_save(user_id, slim)


def _today(u: dict, language: str | None = None) -> dict:
    """Roll the daily counters over on a new day."""
    today = date_type.today().isoformat()
    if u.get("date") != today:
        u.update({"date": today, "jokes_served": 0, "facts_served": 0, "tips_served": 0,
                  "greeting_served": False, "pending_advice": "", "advice_consumed": True})
    if language:
        u["language"] = language
    return u


def _import_legacy_seen(u: dict, state: seen_store.SeenState) -> None:
    """A legacy row listed every seen text; mark those items as seen once."""
    for key, bucket in _LEGACY_SEEN.items():
        texts = set(u.get(key) or [])
        if not texts:
            continue
        b = state.bucket(bucket)
        for i, item in enumerate(BUCKET_ITEMS[bucket]):
            if texts & set(item.tr.values()):
                b.mark(i)


# ─── Serving pool items ───────────────────────────────────────────────────────

def serve_item(user_id: int, bucket: str, language: str, when: Optional[str] = None) -> tuple[Optional[Item], bool]:
    """The next item of a bucket for this user, or (None, True) when today's
    cap is reached, or (None, False) when the language has nothing."""
    lang = iso(language)
    with _lock:
        u = _today(_load_user(user_id), language)
        served_key = _SERVED_KEY.get(bucket)
        if served_key and u.get(served_key, 0) >= DAILY_CAPS[bucket]:
            return None, True
        with seen_store.session(user_id) as state:
            _import_legacy_seen(u, state)
            index = pick_item(state.bucket(bucket), BUCKET_ITEMS[bucket], lang, date_type.today(), when=when)
        if index is None:
            _save_user(user_id, u)
            return None, False
        if served_key:
            u[served_key] = u.get(served_key, 0) + 1
        _save_user(user_id, u)
    return BUCKET_ITEMS[bucket][index], False


def item_text(item: Item, language: str) -> str:
    return _cap(item.text_in(iso(language)) or "")


def item_translations(item: Item) -> dict[str, str]:
    return {lang: _cap(text) for lang, text in item.translations().items()}


def get_next_encouragement(user_id: int, language: str) -> str:
    item, _ = serve_item(user_id, "encouragements", language)
    return item_text(item, language) if item else ""


# ─── Daily flags ──────────────────────────────────────────────────────────────

def _advice_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def get_pending_advice(user_id: int) -> str | None:
    with _lock:
        u = _load_user(user_id)
        if not u.get("pending_advice") or u.get("advice_consumed", True):
            return None
        advice = u["pending_advice"]
        u["advice_consumed"] = True
        # Never serve the same advice twice: remember short hashes, not texts.
        seen = [h for h in u.get("seen_advice", []) if isinstance(h, str) and len(h) <= 16]
        h = _advice_hash(advice)
        if h in seen:
            u["seen_advice"] = seen
            _save_user(user_id, u)
            return None
        u["seen_advice"] = (seen + [h])[-_ADVICE_MEMORY:]
        _save_user(user_id, u)
        return advice


def store_pending_advice(user_id: int, advice: str) -> None:
    with _lock:
        u = _today(_load_user(user_id))
        u["pending_advice"] = advice
        u["advice_consumed"] = False
        _save_user(user_id, u)


def get_greeting_served(user_id: int) -> bool:
    with _lock:
        u = _load_user(user_id)
        return u.get("date") == date_type.today().isoformat() and u.get("greeting_served", False)


def mark_greeting_served(user_id: int) -> None:
    with _lock:
        u = _today(_load_user(user_id))
        u["greeting_served"] = True
        _save_user(user_id, u)


def tip_available_today(user_id: int) -> bool:
    with _lock:
        u = _today(_load_user(user_id))
        return u.get("tips_served", 0) < DAILY_CAPS["tips"]


__all__ = [
    "DAILY_CAPS", "get_greeting_served", "get_next_encouragement", "get_pending_advice", "item_text",
    "item_translations", "iso", "mark_greeting_served", "serve_item", "store_pending_advice",
    "tip_available_today",
]
