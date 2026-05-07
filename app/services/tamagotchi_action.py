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


def get_next_action(user_id: int, language: str) -> NextActionResponse:
    advice = get_pending_advice(user_id)
    if advice is not None:
        return NextActionResponse(type="ADVICE", content=advice, animation_hint="COIN_COLLECT")

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
        return NextActionResponse(type="GREETING", content=greeting, animation_hint="FLY_BY_MOON")

    joke = get_next_joke(user_id, language)
    if joke is not None:
        return NextActionResponse(type="JOKE", content=joke, animation_hint="COW_ABDUCTION")

    fact = get_next_fact(user_id, language)
    if fact is not None:
        return NextActionResponse(type="FACT", content=fact, animation_hint="COIN_COLLECT")

    # Encouragement when daily jokes/facts are exhausted — 60% chance, else animation
    if random.random() < 0.6:
        lang_encouragements = ENCOURAGEMENTS.get(language.upper(), ENCOURAGEMENTS["EN"])
        return NextActionResponse(
            type="ENCOURAGEMENT",
            content=random.choice(lang_encouragements),
            animation_hint="COIN_COLLECT",
        )

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
