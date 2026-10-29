"""
Companion message renderer — the wording half of the tamagotchi.

Go owns the companion: it decides WHAT to say and WHEN (health, mood and a
prioritized message type with the real numbers it needs). This module only
turns that (type, tone, language, numbers) into one text variant, never
repeating the variant the user saw last for that type.

Variants live in ``app.data.companion_messages.COMPANION_VARIANTS`` (filled by
Stage D). A type with no variant returns None and the client uses its own
four-language fallback, so the companion works before Stage D lands.

Recently-shown variants are remembered in process memory only: losing that on
a restart just means one possible repeat, and it keeps the companion's state
out of the AI service (Go's companion_states row is the only stored state).
"""
from __future__ import annotations

import random
import threading
from collections import deque
from typing import Any, Mapping, Optional

from app.data.companion_messages import COMPANION_VARIANTS

# Slots holding money amounts; they are formatted with the user's currency.
AMOUNT_SLOTS = frozenset({"amount", "remaining", "daily", "spent", "over", "saved_total", "forecast_end"})

_CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "UAH": "₴", "RUB": "₽", "PLN": "zł", "CHF": "CHF "}

_recent: dict[tuple[int, str], deque[int]] = {}
_lock = threading.Lock()


def format_amount(value: float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get((currency or "").upper(), f"{currency} " if currency else "")
    sign = "−" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):.2f}"


def _format_slots(slots: Mapping[str, Any], currency: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in slots.items():
        if key in AMOUNT_SLOTS and isinstance(value, (int, float)):
            out[key] = format_amount(float(value), currency)
        elif isinstance(value, float) and value.is_integer():
            out[key] = str(int(value))
        else:
            out[key] = str(value)
    return out


def _variants(pool: Mapping[str, Mapping[str, list[str]]], type_: str, language: str, tone: str) -> list[str]:
    by_lang = pool.get(type_, {})
    lang = language.lower()
    return list(by_lang.get(f"{lang}:{tone}") or by_lang.get(lang) or [])


def render_message(
    user_id: int,
    type_: str,
    tone: str,
    language: str,
    slots: Mapping[str, Any],
    currency: str = "",
    pool: Optional[Mapping[str, Mapping[str, list[str]]]] = None,
) -> Optional[str]:
    """One variant for (type, tone, language) with its numbers filled in, or
    None when there is no usable variant (the client falls back)."""
    variants = _variants(COMPANION_VARIANTS if pool is None else pool, type_, language, tone)
    if not variants:
        return None
    values = _format_slots(slots, currency)
    key = (user_id, type_)
    with _lock:
        recent = _recent.setdefault(key, deque(maxlen=max(1, len(variants) - 1)))
        order = [i for i in range(len(variants)) if i not in recent] or list(range(len(variants)))
        random.shuffle(order)
        for i in order:
            try:
                text = variants[i].format_map(values)
            except (KeyError, IndexError, ValueError):
                continue  # this variant needs a number the message lacks
            recent.append(i)
            return text
    return None
