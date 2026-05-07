from __future__ import annotations

import random
from datetime import datetime

from app.data.content import ENCOURAGEMENTS, GREETINGS
from app.models.response import NextActionResponse
from app.services.content_tracker import (
    get_greeting_served,
    get_next_fact,
    get_next_joke,
    get_pending_advice,
    is_apology_mode,
    mark_greeting_served,
)

_ANIMATION_HINTS = ["COW_ABDUCTION", "COIN_COLLECT", "FLY_BY_MOON"]

_APOLOGY_PREFIXES: dict[str, list[str]] = {
    "EN": ["🌙 Back! ", "🛸 Again! ", "One more: "],
    "RU": ["🌙 Снова! ", "🛸 Ещё раз! ", "Попробуем: "],
    "UA": ["🌙 Знову! ", "🛸 Ще раз! ", "Спробуємо: "],
    "DE": ["🌙 Zurück! ", "🛸 Nochmal! ", "Einmal noch: "],
}


def _cap(text: str) -> str:
    return text if len(text) <= 99 else text[:99] + "…"


def _get_time_segment() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _apply_apology(content: str, language: str) -> str:
    prefixes = _APOLOGY_PREFIXES.get(language.upper(), _APOLOGY_PREFIXES["EN"])
    prefix = random.choice(prefixes)
    return prefix + content[: 99 - len(prefix)]


def get_next_action(user_id: int, language: str) -> NextActionResponse:
    apology = is_apology_mode(user_id)

    advice = get_pending_advice(user_id)
    if advice is not None:
        content = _apply_apology(advice, language) if apology else advice
        return NextActionResponse(type="ADVICE", content=content, animation_hint="COIN_COLLECT")

    # Time-aware greeting — shown once per day on first interaction
    if not get_greeting_served(user_id):
        segment = _get_time_segment()
        lang_greetings = GREETINGS.get(language.upper(), GREETINGS["EN"])
        greeting = _cap(random.choice(lang_greetings[segment]))
        mark_greeting_served(user_id)
        return NextActionResponse(type="GREETING", content=greeting, animation_hint="FLY_BY_MOON")

    joke = get_next_joke(user_id, language)
    if joke is not None:
        content = _apply_apology(joke, language) if apology else joke
        return NextActionResponse(type="JOKE", content=content, animation_hint="COW_ABDUCTION")

    fact = get_next_fact(user_id, language)
    if fact is not None:
        content = _apply_apology(fact, language) if apology else fact
        return NextActionResponse(type="FACT", content=content, animation_hint="COIN_COLLECT")

    # Encouragement when daily jokes/facts are exhausted — 60% chance, else animation
    if random.random() < 0.6:
        lang_encouragements = ENCOURAGEMENTS.get(language.upper(), ENCOURAGEMENTS["EN"])
        encouragement = _cap(random.choice(lang_encouragements))
        return NextActionResponse(type="ENCOURAGEMENT", content=encouragement, animation_hint="COIN_COLLECT")

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
