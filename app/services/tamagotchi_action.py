from __future__ import annotations

import random

from app.models.response import NextActionResponse
from app.services.content_tracker import get_next_fact, get_next_joke, get_pending_advice

_ANIMATION_HINTS = ["COW_ABDUCTION", "COIN_COLLECT", "FLY_BY_MOON"]


def get_next_action(user_id: int, language: str) -> NextActionResponse:
    advice = get_pending_advice(user_id)
    if advice is not None:
        return NextActionResponse(type="ADVICE", content=advice, animation_hint="COIN_COLLECT")

    joke = get_next_joke(user_id, language)
    if joke is not None:
        return NextActionResponse(type="JOKE", content=joke, animation_hint="COW_ABDUCTION")

    fact = get_next_fact(user_id, language)
    if fact is not None:
        return NextActionResponse(type="FACT", content=fact, animation_hint="COIN_COLLECT")

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
