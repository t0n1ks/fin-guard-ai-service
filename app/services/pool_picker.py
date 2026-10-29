"""
Choosing pool items without repeats.

Items (jokes, facts, tips, …):
  1. Serve a random item the user has not seen yet, in their language.
  2. When everything available has been seen, repeats may begin (avoiding the
     last few shown) — but the seen-set is RESET only when the current pass
     began at least RESET_AFTER_DAYS ago. Unseen items are never skipped by a
     reset, and items added later start unseen, so they come first.

Message variants: any variant whose numbers are all available and that suits
the context, never one of the last few used for that message type.
"""
from __future__ import annotations

import random
from datetime import date
from typing import Callable, Optional, Sequence

from app.data.pool.model import Item
from app.services.seen_store import RECENT, Bucket, remember

RESET_AFTER_DAYS = 60
EPOCH = date(2024, 1, 1)


def day_number(d: date) -> int:
    """1-based day counter (0 is reserved for "never")."""
    return (d - EPOCH).days + 1


def pick_item(
    bucket: Bucket,
    items: Sequence[Item],
    lang: str,
    today: date,
    rng: random.Random | None = None,
    when: Optional[str] = None,
) -> Optional[int]:
    """Index of the item to show (and records it), or None if the language has none."""
    rng = rng or random.Random()
    available = [i for i, it in enumerate(items) if it.text_in(lang) and (when is None or it.when == when)]
    if not available:
        return None
    if bucket.cycle_day == 0:
        bucket.cycle_day = day_number(today)

    unseen = [i for i in available if not bucket.seen(i)]
    if not unseen and day_number(today) - bucket.cycle_day >= RESET_AFTER_DAYS:
        for i in available:  # a new pass over what this user can see
            if i // 8 < len(bucket.bits):
                bucket.bits[i // 8] &= ~(1 << (i % 8)) & 0xFF
        bucket.cycle_day = day_number(today)
        unseen = available

    if unseen:
        choice = rng.choice(unseen)
        bucket.mark(choice)
    else:  # exhausted, too early to reset: repeat, but not the latest ones
        fresh = [i for i in available if i not in bucket.recent] or available
        choice = rng.choice(fresh)
    bucket.remember(choice)
    return choice


def pick_variant(
    recent: list[int],
    variants: Sequence[Item],
    lang: str,
    render: Callable[[Item], Optional[str]],
    rng: random.Random | None = None,
) -> Optional[str]:
    """A rendered variant that is not among the last few used, or None."""
    rng = rng or random.Random()
    usable: list[tuple[int, str]] = []
    for i, v in enumerate(variants):
        if v.text_in(lang) is None:
            continue
        text = render(v)
        if text is not None:
            usable.append((i, text))
    if not usable:
        return None
    avoid = set(recent[-min(RECENT, len(usable) - 1):]) if len(usable) > 1 else set()
    fresh = [u for u in usable if u[0] not in avoid] or usable
    index, text = rng.choice(fresh)
    remember(recent, index)
    return text
