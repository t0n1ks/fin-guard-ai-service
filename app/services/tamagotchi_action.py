from __future__ import annotations

import random
from datetime import datetime

from app.data.content import (
    BUDGET_TIPS,
    CHEERFUL_GREETINGS,
    GREETINGS,
    GRUMPY_GREETINGS,
    STATISTICS,
)
from app.models.response import NextActionResponse
from app.services.content_tracker import (
    get_greeting_served,
    get_next_budget_tip,
    get_next_encouragement,
    get_next_fact,
    get_next_joke,
    get_next_statistic,
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


# Budget-health → joke probability. Drives context-aware proactive content:
# over budget keeps it serious (no jokes, lean on facts/tips); comfortably under
# allows lighter humor. Absent/unknown context falls back to the original 0.3.
_JOKE_PROB_BY_CONTEXT = {"over": 0.0, "warn": 0.15, "good": 0.45}


def get_categorized_content(
    user_id: int,
    language: str,
    category: str,
    context: str | None = None,
) -> NextActionResponse:
    """Return a single content item of an explicit, fixed category.

    Used by the user-initiated UFO entities (Cow → joke, Star → fact) and the
    transaction-triggered advice path. Strictly category-locked: unlike
    get_next_action it never falls through to a different type. When the pool is
    exhausted/capped (or no advice is pending) it returns type="NONE" so the
    caller can fall back to its local i18n pool. `context` is accepted for
    parity/logging; the category is never overridden by it.
    """
    cat = (category or "").strip().lower()

    if cat == "advice":
        advice = get_pending_advice(user_id)
        if advice:
            return _build_response("ADVICE", advice, "COIN_COLLECT", language, user_id=user_id)
        return NextActionResponse(type="NONE", content=None, animation_hint="FLY_BY_MOON")

    # Note: user_id is deliberately NOT passed to _build_response for joke/fact.
    # That keeps the categories strict — a joke is only ever a real joke (or NONE);
    # the <5-char encouragement substitution in _build_response can never leak
    # advice/encouragement content into the humor (Cow) or fact (Star) channels.
    # Explicit user clicks bypass the daily pacing cap so every Cow/Star tap
    # returns a fresh unseen item, cycling the whole pool before any repeat.
    if cat == "joke":
        content, translations = get_next_joke(user_id, language, enforce_daily_cap=False)
        if content is not None:
            return _build_response("JOKE", content, "COW_ABDUCTION", language, translations)
        return NextActionResponse(type="NONE", content=None, animation_hint="COW_ABDUCTION")

    if cat == "fact":
        content, translations = get_next_fact(user_id, language, enforce_daily_cap=False)
        if content is not None:
            return _build_response("FACT", content, "COIN_COLLECT", language, translations)
        return NextActionResponse(type="NONE", content=None, animation_hint="COIN_COLLECT")

    return NextActionResponse(type="NONE", content=None, animation_hint="FLY_BY_MOON")


def get_next_action(user_id: int, language: str, context: str | None = None) -> NextActionResponse:
    advice = get_pending_advice(user_id)
    if advice is not None:
        return _build_response("ADVICE", advice, "COIN_COLLECT", language, user_id=user_id)

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
        return _build_response("GREETING", greeting, "FLY_BY_MOON", language, user_id=user_id)

    # Context-aware jokes/facts ordering — probabilistic, fall through if one pool exhausted
    joke_prob = _JOKE_PROB_BY_CONTEXT.get((context or "").strip().lower(), 0.3)
    if random.random() < joke_prob:
        first_fn, first_type, first_hint = get_next_joke, "JOKE", "COW_ABDUCTION"
        second_fn, second_type, second_hint = get_next_fact, "FACT", "COIN_COLLECT"
    else:
        first_fn, first_type, first_hint = get_next_fact, "FACT", "COIN_COLLECT"
        second_fn, second_type, second_hint = get_next_joke, "JOKE", "COW_ABDUCTION"

    content, translations = first_fn(user_id, language)
    if content is not None:
        return _build_response(first_type, content, first_hint, language, translations, user_id=user_id)

    content, translations = second_fn(user_id, language)
    if content is not None:
        return _build_response(second_type, content, second_hint, language, translations, user_id=user_id)

    # Budget tips / statistics when joke+fact daily limits are exhausted
    if random.random() < 0.5:
        tip_fn, tip_type = get_next_budget_tip, "BUDGET_TIPS"
        stat_fn, stat_type = get_next_statistic, "STATISTICS"
    else:
        tip_fn, tip_type = get_next_statistic, "STATISTICS"  # type: ignore[assignment]
        stat_fn, stat_type = get_next_budget_tip, "BUDGET_TIPS"  # type: ignore[assignment]

    content, translations = tip_fn(user_id, language)
    if content is not None:
        return _build_response(tip_type, content, "COIN_COLLECT", language, translations, user_id=user_id)

    content, translations = stat_fn(user_id, language)
    if content is not None:
        return _build_response(stat_type, content, "COIN_COLLECT", language, translations, user_id=user_id)

    # Encouragement when all content pools exhausted — 60% chance, else animation
    if random.random() < 0.6:
        enc = get_next_encouragement(user_id, language)
        return _build_response("ENCOURAGEMENT", enc, "COIN_COLLECT", language, user_id=user_id)

    return NextActionResponse(
        type="RANDOM_ANIMATION",
        content=None,
        animation_hint=random.choice(_ANIMATION_HINTS),
    )
