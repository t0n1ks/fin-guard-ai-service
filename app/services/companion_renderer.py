"""
Companion message renderer — the wording half of the tamagotchi.

Go owns the companion: it decides WHAT to say and WHEN (health, mood and a
prioritized message type with the real numbers it needs). This module only
turns that (type, tone, language, numbers) into one variant from the pool
(``app.data.pool.messages``), with the numbers written the way the language
writes them, never one of the last few variants the user saw for that type.

Variants that need a number the message does not carry are skipped, and
``when="calibrating"`` variants are only used while Go flags the first week
of a period. No usable variant → None, and the app uses its own fallback.
The per-type "recently used" memory lives in the user's compact seen row.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from app.data.pool import MESSAGES
from app.data.pool.model import Item
from app.services import seen_store
from app.services.locale_format import format_amount, format_slots
from app.services.pool_picker import pick_variant

__all__ = ["format_amount", "render_message"]


def _suits(variant: Item, slots: Mapping[str, Any]) -> bool:
    if variant.when is None:
        return True
    return variant.when == "calibrating" and bool(slots.get("calibrating"))


def render_message(
    user_id: int,
    type_: str,
    tone: str,
    language: str,
    slots: Mapping[str, Any],
    currency: str = "",
    pool: Optional[Mapping[str, list[Item]]] = None,
) -> Optional[str]:
    """One variant for (type, language) with its numbers filled in, or None.
    ``tone`` is accepted for the interface; the variants carry their tone."""
    variants = (MESSAGES if pool is None else pool).get(type_, [])
    if not variants:
        return None
    values = format_slots(slots, currency, language)

    def render(v: Item) -> Optional[str]:
        if not _suits(v, slots):
            return None
        try:
            return (v.text_in(language) or "").format_map(values) or None
        except (KeyError, IndexError, ValueError):
            return None  # needs a number this message lacks

    if type_ not in seen_store.MESSAGE_TYPES:
        return pick_variant([], variants, language, render)
    with seen_store.session(user_id) as state:
        return pick_variant(state.message_recent(type_), variants, language, render)
