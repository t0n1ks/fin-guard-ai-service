from __future__ import annotations

import random
from datetime import datetime

from app.data.content import (
    CHEERFUL_GREETINGS,
    ENCOURAGEMENTS,
    GREETINGS,
    GRUMPY_GREETINGS,
)
from app.models.response import NextActionResponse
from app.services.content_tracker import (
    get_greeting_served,
    get_next_fact,
    get_next_joke,
    get_pending_advice,
    mark_greeting_served,
)
from app.services.visit_tracker import get_visit_mood

_ANIMATION_HINTS = ["COW_ABDUCTION", "COIN_COLLECT", "FLY_BY_MOON"]


def _get_time_segment() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _enforce_length(text: str, limit: int = 140) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _build_response(type_: str, content: str | None, hint: str, language: str) -> NextActionResponse:
    text = (content or "").strip()
    if len(text) < 5:
        enc = ENCOURAGEMENTS.get(language.upper(), ENCOURAGEMENTS["EN"])
        text = random.choice(enc)
    return NextActionResponse(type=type_, content=_enforce_length(text), animation_hint=hint)


def get_next_action(user_id: int, language: str) -> NextActionResponse:
    advice = get_pending_advice(user_id)
    if advice is not None:
        return _build_response("ADVICE", advice, "COIN_COLLECT", language)

    # Time-aware / mood-aware greeting — shown once per day on first interaction
    if not get_greeting_served(user_id):
        lang_up = language.upper()
        mood = get_visit_mood(user_id)

        if mood == "cheerful":
            pool = CHEERFUL_GREETINGS.get(lang_up, CHEERFUL_GREETINGS["EN"])
        elif mood == "grumpy":
            pool = GRUMPY_GREETINGS.get(lang_up, GRUMPY_GREETINGS["EN"])
        else:
            segment = _get_time_segment()
            pool = GREETINGS.get(lang_up, GREETINGS["EN"])[segment]

        greeting = random.choice(pool)
        mark_greeting_served(user_id)
        return _build_response("GREETING", greeting, "FLY_BY_MOON", language)

    # 30% jokes / 70% facts — probabilistic ordering, fall through if one pool exhausted
    if random.random() < 0.3:
        first_fn, first_type, first_hint = get_next_joke, "JOKE", "COW_ABDUCTION"
        second_fn, second_type, second_hint = get_next_fact, "FACT", "COIN_COLLECT"
    else:
        first_fn, first_type, first_hint = get_next_fact, "FACT", "COIN_COLLECT"
        second_fn, second_type, second_hint = get_next_joke, "JOKE", "COW_ABDUCTION"

    content = first_fn(user_id, language)
    if content is not None:
        return _build_response(first_type, content, first_hint, language)

    content = second_fn(user_id, language)
    if content is not None:
        return _build_response(second_type, content, second_hint, language)

    # Encouragement when daily limits are exhausted — 60% chance, else animation
    if random.random() < 0.6:
        lang_encouragements = ENCOURAGEMENTS.get(language.upper(), ENCOURAGEMENTS["EN"])
        return _build_response("ENCOURAGEMENT", random.choice(lang_encouragements), "COIN_COLLECT", language)

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
