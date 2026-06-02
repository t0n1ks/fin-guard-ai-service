from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import threading
from datetime import date as date_type

from app.data.content import BUDGET_TIPS, ENCOURAGEMENTS, FACTS, JOKES, STATISTICS

# Maps Python content-dict keys to frontend ISO codes
_LANG_NORM: dict[str, str] = {"EN": "en", "DE": "de", "RU": "ru", "UA": "uk"}

logger = logging.getLogger(__name__)

def _cap(text: str) -> str:
    return text if len(text) <= 140 else text[:139] + "…"

# ─── Storage backend ──────────────────────────────────────────────────────────

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)

_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "daily_state.json")
_lock = threading.Lock()


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

def _reset_category(u: dict, queue_key: str, seen_key: str, pool: dict[str, list[str]], language: str) -> None:
    """Cycle reset: refill a category's queue from the full pool (reshuffled) and
    clear its seen-list. Called when the unseen queue is exhausted so the user
    starts a fresh non-repeating cycle through the whole pool."""
    items = list(pool.get(language, pool.get("EN", [])))
    random.shuffle(items)
    u[queue_key] = items
    u[seen_key] = []


def _ensure_user_state(state: dict, user_id: int, language: str, today: str) -> None:
    key = str(user_id)
    existing = state.get(key, {})
    same_day = existing.get("date") == today
    same_lang = existing.get("language") == language

    if same_day and same_lang:
        # Backfill seen lists for state created before this feature
        if "seen_jokes" not in existing:
            existing["seen_jokes"] = []
        if "seen_facts" not in existing:
            existing["seen_facts"] = []
        if "seen_budget_tips" not in existing:
            existing["seen_budget_tips"] = []
        if "seen_stats" not in existing:
            existing["seen_stats"] = []
        if "seen_advice" not in existing:
            existing["seen_advice"] = []
        state[key] = existing
        return

    all_jokes = list(JOKES.get(language, JOKES["EN"]))
    all_facts = list(FACTS.get(language, FACTS["EN"]))
    all_budget_tips = list(BUDGET_TIPS.get(language, BUDGET_TIPS["EN"]))
    all_stats = list(STATISTICS.get(language, STATISTICS["EN"]))

    if same_lang:
        # Carry cross-day seen lists forward
        seen_jokes: list = existing.get("seen_jokes", [])
        seen_facts: list = existing.get("seen_facts", [])
        seen_budget_tips: list = existing.get("seen_budget_tips", [])
        seen_stats: list = existing.get("seen_stats", [])
    else:
        # Language changed — start fresh
        seen_jokes = []
        seen_facts = []
        seen_budget_tips = []
        seen_stats = []

    # Build today's queue from unseen items only
    unseen_jokes = [j for j in all_jokes if j not in seen_jokes]
    if not unseen_jokes:
        seen_jokes = []
        unseen_jokes = list(all_jokes)

    unseen_facts = [f for f in all_facts if f not in seen_facts]
    if not unseen_facts:
        seen_facts = []
        unseen_facts = list(all_facts)

    unseen_budget_tips = [b for b in all_budget_tips if b not in seen_budget_tips]
    if not unseen_budget_tips:
        seen_budget_tips = []
        unseen_budget_tips = list(all_budget_tips)

    unseen_stats = [s for s in all_stats if s not in seen_stats]
    if not unseen_stats:
        seen_stats = []
        unseen_stats = list(all_stats)

    random.shuffle(unseen_jokes)
    random.shuffle(unseen_facts)
    random.shuffle(unseen_budget_tips)
    random.shuffle(unseen_stats)

    # Encouragement + advice no-repeat: reset cross-language but preserve cross-day
    if same_lang:
        seen_encouragements: list = existing.get("seen_encouragements", [])
        seen_advice: list = existing.get("seen_advice", [])
    else:
        seen_encouragements = []
        seen_advice = []

    all_encouragements = list(ENCOURAGEMENTS.get(language, ENCOURAGEMENTS["EN"]))
    unseen_encouragements = [e for e in all_encouragements if e not in seen_encouragements]
    if not unseen_encouragements:
        seen_encouragements = []
        unseen_encouragements = list(all_encouragements)
    random.shuffle(unseen_encouragements)

    state[key] = {
        "date": today,
        "language": language,
        "joke_queue": unseen_jokes,
        "fact_queue": unseen_facts,
        "budget_tip_queue": unseen_budget_tips,
        "stat_queue": unseen_stats,
        "jokes_served": 0,
        "facts_served": 0,
        "budget_tips_served": 0,
        "stats_served": 0,
        "seen_jokes": seen_jokes,
        "seen_facts": seen_facts,
        "seen_budget_tips": seen_budget_tips,
        "seen_stats": seen_stats,
        "encouragement_queue": unseen_encouragements,
        "seen_encouragements": seen_encouragements,
        # Persistent advice de-dup — carried across days (same language) so the
        # same nudge is never repeated, while the frontend list still resets daily.
        "seen_advice": seen_advice,
        # Preserve pending advice only when it was generated in the same language today
        "pending_advice": existing.get("pending_advice", "") if (same_day and same_lang) else "",
        "advice_consumed": existing.get("advice_consumed", True) if (same_day and same_lang) else True,
        "greeting_served": existing.get("greeting_served", False) if same_day else False,
    }


# ─── Public API ───────────────────────────────────────────────────────────────

def _build_translations(text: str, source: dict[str, list[str]], language: str) -> dict[str, str]:
    """Return all-language translations for a content item located by its text in the source dict."""
    lang_up = language.upper()
    source_list = list(source.get(lang_up, source.get("EN", [])))
    try:
        idx = source_list.index(text)
    except ValueError:
        return {_LANG_NORM.get(lang_up, lang_up.lower()): _cap(text)}
    translations: dict[str, str] = {}
    for code, items in source.items():
        if idx < len(items):
            iso = _LANG_NORM.get(code, code.lower())
            translations[iso] = _cap(items[idx])
    return translations


def get_next_joke(
    user_id: int, language: str, enforce_daily_cap: bool = True
) -> tuple[str | None, dict[str, str]]:
    """Return the next unseen joke. enforce_daily_cap is True for the proactive
    channel (pacing); explicit Cow clicks pass False so every click yields a
    fresh unseen joke, cycling through the whole pool before any repeat."""
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if enforce_daily_cap and u["jokes_served"] >= 3:
            return None, {}
        if not u["joke_queue"]:
            _reset_category(u, "joke_queue", "seen_jokes", JOKES, language)
        if not u["joke_queue"]:
            return None, {}  # pool genuinely empty for this language

        joke = u["joke_queue"].pop(0)
        u["jokes_served"] += 1
        seen: list = u.setdefault("seen_jokes", [])
        if joke not in seen:
            seen.append(joke)
        _save_state(state)
        return _cap(joke), _build_translations(joke, JOKES, language)


def get_next_fact(
    user_id: int, language: str, enforce_daily_cap: bool = True
) -> tuple[str | None, dict[str, str]]:
    """Return the next unseen fact. See get_next_joke for the cap semantics."""
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if enforce_daily_cap and u["facts_served"] >= 5:
            return None, {}
        if not u["fact_queue"]:
            _reset_category(u, "fact_queue", "seen_facts", FACTS, language)
        if not u["fact_queue"]:
            return None, {}  # pool genuinely empty for this language

        fact = u["fact_queue"].pop(0)
        u["facts_served"] += 1
        seen: list = u.setdefault("seen_facts", [])
        if fact not in seen:
            seen.append(fact)
        _save_state(state)
        return _cap(fact), _build_translations(fact, FACTS, language)


def get_next_encouragement(user_id: int, language: str) -> str:
    """Return the next unseen encouragement for the user, cycling through all before repeating."""
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        queue: list = u.get("encouragement_queue", [])
        if not queue:
            # Exhausted — rebuild and reshuffle
            all_enc = list(ENCOURAGEMENTS.get(language.upper(), ENCOURAGEMENTS["EN"]))
            random.shuffle(all_enc)
            u["encouragement_queue"] = all_enc
            u["seen_encouragements"] = []
            queue = u["encouragement_queue"]

        enc = queue.pop(0)
        seen_enc: list = u.setdefault("seen_encouragements", [])
        if enc not in seen_enc:
            seen_enc.append(enc)
        _save_state(state)
        return _cap(enc)


def get_pending_advice(user_id: int) -> str | None:
    with _lock:
        state = _load_state()
        key = str(user_id)
        u = state.get(key, {})

        if not u.get("pending_advice") or u.get("advice_consumed", True):
            return None

        advice = u["pending_advice"]
        u["advice_consumed"] = True

        # Persistent de-dup: never serve the same advice text twice (across days).
        # Nudges vary with the user's situation, so this won't starve — a duplicate
        # simply yields None and the frontend falls back to its local pacing pool.
        seen_adv: list = u.setdefault("seen_advice", [])
        if advice in seen_adv:
            state[key] = u
            _save_state(state)
            return None
        seen_adv.append(advice)
        if len(seen_adv) > 100:
            del seen_adv[:-100]  # bound growth — keep the most recent 100

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
                "seen_jokes": existing.get("seen_jokes", []),
                "seen_facts": existing.get("seen_facts", []),
                "seen_advice": existing.get("seen_advice", []),
                "pending_advice": advice,
                "advice_consumed": False,
                "greeting_served": False,
            }

        _save_state(state)


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


def get_next_budget_tip(user_id: int, language: str) -> tuple[str | None, dict[str, str]]:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if u.get("budget_tips_served", 0) >= 3 or not u.get("budget_tip_queue"):
            return None, {}

        tip = u["budget_tip_queue"].pop(0)
        u["budget_tips_served"] = u.get("budget_tips_served", 0) + 1
        seen: list = u.setdefault("seen_budget_tips", [])
        if tip not in seen:
            seen.append(tip)
        _save_state(state)
        return _cap(tip), _build_translations(tip, BUDGET_TIPS, language)


def get_next_statistic(user_id: int, language: str) -> tuple[str | None, dict[str, str]]:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        _ensure_user_state(state, user_id, language, today)
        u = state[str(user_id)]

        if u.get("stats_served", 0) >= 5 or not u.get("stat_queue"):
            return None, {}

        stat = u["stat_queue"].pop(0)
        u["stats_served"] = u.get("stats_served", 0) + 1
        seen: list = u.setdefault("seen_stats", [])
        if stat not in seen:
            seen.append(stat)
        _save_state(state)
        return _cap(stat), _build_translations(stat, STATISTICS, language)
