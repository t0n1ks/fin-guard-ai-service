from __future__ import annotations

import json
import os
import random
import tempfile
import threading
from datetime import date as date_type

from app.data.content import FACTS, JOKES


def _cap(text: str) -> str:
    return text if len(text) <= 99 else text[:99] + "…"

_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "daily_state.json")
_lock = threading.Lock()


def _load_state() -> dict:
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
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

    state[key] = {
        "date": today,
        "language": language,
        "joke_queue": jokes,
        "fact_queue": facts,
        "jokes_served": 0,
        "facts_served": 0,
        # preserve same-day advice across language switches; wipe on new day
        "pending_advice": existing.get("pending_advice", "") if same_day else "",
        "advice_consumed": existing.get("advice_consumed", True) if same_day else True,
        "rejections_today": existing.get("rejections_today", 0) if same_day else 0,
    }


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

        # preserve queue state for the day; only update advice fields
        if existing.get("date") == today:
            existing["pending_advice"] = advice
            existing["advice_consumed"] = False
            state[key] = existing
        else:
            # new day — initialize minimal entry; queues will be built on first content call
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
            }

        _save_state(state)


def is_apology_mode(user_id: int) -> bool:
    with _lock:
        state = _load_state()
        today = date_type.today().isoformat()
        u = state.get(str(user_id), {})
        return u.get("date") == today and u.get("rejections_today", 0) >= 2
