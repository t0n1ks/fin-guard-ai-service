from __future__ import annotations

import random

from app.models.response import NextActionResponse
from app.services.content_tracker import (
    get_next_fact,
    get_next_joke,
    get_pending_advice,
    is_apology_mode,
)

_ANIMATION_HINTS = ["COW_ABDUCTION", "COIN_COLLECT", "FLY_BY_MOON"]

_APOLOGY_PREFIXES: dict[str, list[str]] = {
    "EN": ["🌙 Back! ", "🛸 Again! ", "One more: "],
    "RU": ["🌙 Снова! ", "🛸 Ещё раз! ", "Попробуем: "],
    "UA": ["🌙 Знову! ", "🛸 Ще раз! ", "Спробуємо: "],
    "DE": ["🌙 Zurück! ", "🛸 Nochmal! ", "Einmal noch: "],
}


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

    joke = get_next_joke(user_id, language)
    if joke is not None:
        content = _apply_apology(joke, language) if apology else joke
        return NextActionResponse(type="JOKE", content=content, animation_hint="COW_ABDUCTION")

    fact = get_next_fact(user_id, language)
    if fact is not None:
        content = _apply_apology(fact, language) if apology else fact
        return NextActionResponse(type="FACT", content=content, animation_hint="COIN_COLLECT")

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
