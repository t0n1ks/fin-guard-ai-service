from __future__ import annotations

import random
from datetime import date

from app.data.content import (
    CHEERFUL_GREETINGS,
    GREETINGS,
    GRUMPY_GREETINGS,
)
from app.models.response import NextActionResponse
from app.services.content_tracker import (
    get_greeting_served,
    get_next_encouragement,
    get_pending_advice,
    item_text,
    item_translations,
    mark_greeting_served,
    serve_item,
    tip_available_today,
)
from app.services.user_day import resolve_hour
from app.services.visit_tracker import get_visit_mood

_ANIMATION_HINTS = ["COW_ABDUCTION", "COIN_COLLECT", "FLY_BY_MOON"]

# Category → (pool bucket, response type, animation hint).
_CATEGORY_BUCKETS = {
    "joke": ("jokes", "JOKE", "COW_ABDUCTION"),
    "fact": ("facts", "FACT", "COIN_COLLECT"),
    "exit": ("exits", "EXIT", "FLY_BY_MOON"),
}


def _get_time_segment(hour: int) -> str:
    """The greeting's part of the day for the user's LOCAL hour (0–23)."""
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _enforce_length(text: str, limit: int = 140) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _build_response(
    type_: str,
    content: str | None,
    hint: str,
    language: str,
    translations: dict[str, str] | None = None,
    user_id: int | None = None,
) -> NextActionResponse:
    text = (content or "").strip()
    if len(text) < 5 and user_id is not None:
        text = get_next_encouragement(user_id, language)
    return NextActionResponse(
        type=type_,
        content=_enforce_length(text),
        animation_hint=hint,
        all_translations=translations if translations else None,
    )


def _none(hint: str = "FLY_BY_MOON") -> NextActionResponse:
    return NextActionResponse(type="NONE", content=None, animation_hint=hint)


def get_categorized_content(
    user_id: int,
    language: str,
    category: str,
    context: str | None = None,
    today: date | None = None,
) -> NextActionResponse:
    """A single item of an explicit, fixed category.

    The cow asks for a "joke", the star for a "fact", a closed message for an
    "exit" line; "advice" is the transaction-advice path. Strictly
    category-locked: never falls through to another type. Jokes and facts
    follow the daily cap (2 each): past it, the cow / star answer with a
    short QUOTA line instead, so the 90-day no-repeat promise holds. NONE
    lets the caller fall back to its own built-in lines. ``context`` is
    accepted for parity/logging only; ``today`` is the user's local date.
    """
    cat = (category or "").strip().lower()

    if cat == "advice":
        advice = get_pending_advice(user_id)
        if advice:
            return _build_response("ADVICE", advice, "COIN_COLLECT", language, user_id=user_id)
        return _none()

    if cat not in _CATEGORY_BUCKETS:
        return _none()
    bucket, type_, hint = _CATEGORY_BUCKETS[cat]
    item, capped = serve_item(user_id, bucket, language, today=today)
    if item is not None:
        return _build_response(type_, item_text(item, language), hint, language, item_translations(item))
    if capped:
        line, _ = serve_item(user_id, "quota", language, when=cat, today=today)
        if line is not None:
            return _build_response("QUOTA", item_text(line, language), hint, language, item_translations(line))
    return _none(hint)


def get_next_action(user_id: int, language: str, context: str | None = None,
                    today: date | None = None, hour: int | None = None) -> NextActionResponse:
    """The ambient channel: pending advice, the daily greeting, at most one tip
    a day, else an encouragement or a quiet animation. Jokes and facts are
    never served here — they belong to the cow and the star (and their caps)."""
    advice = get_pending_advice(user_id)
    if advice is not None:
        return _build_response("ADVICE", advice, "COIN_COLLECT", language, user_id=user_id)

    # Time-aware / mood-aware greeting — shown once per day on first interaction
    if not get_greeting_served(user_id, today):
        lang_up = language.upper()
        mood = get_visit_mood(user_id)

        if mood == "cheerful":
            pool = CHEERFUL_GREETINGS.get(lang_up, CHEERFUL_GREETINGS["EN"])
        elif mood == "grumpy":
            pool = GRUMPY_GREETINGS.get(lang_up, GRUMPY_GREETINGS["EN"])
        else:
            segment = _get_time_segment(resolve_hour(hour))
            pool = GREETINGS.get(lang_up, GREETINGS["EN"])[segment]

        greeting = random.choice(pool)
        mark_greeting_served(user_id, today)
        return _build_response("GREETING", greeting, "FLY_BY_MOON", language, user_id=user_id)

    if tip_available_today(user_id, today):
        tip, _ = serve_item(user_id, "tips", language, today=today)
        if tip is not None:
            return _build_response("TIP", item_text(tip, language), "COIN_COLLECT", language, item_translations(tip))

    # Encouragement 60% of the time, else just an animation.
    if random.random() < 0.6:
        enc = get_next_encouragement(user_id, language, today)
        if enc:
            return _build_response("ENCOURAGEMENT", enc, "COIN_COLLECT", language)

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
