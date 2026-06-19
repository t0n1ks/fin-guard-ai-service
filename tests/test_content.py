"""Integrity guards for the Tamagotchi content pools.

These protect the localization contract the frontend relies on: every language
must have the SAME number of items in the SAME order (the index is the join key
used by `_build_translations` and the frontend keyed registry), with no
duplicates and within the 140-char display cap.
"""

from app.data.content import FACTS, JOKES
from app.services.content_tracker import _LANG_NORM, _build_translations

LANGS = ["EN", "RU", "UA", "DE"]


def _check_pool(pool: dict[str, list[str]], min_items: int) -> None:
    assert set(LANGS) <= set(pool.keys()), f"missing languages: {set(LANGS) - set(pool)}"
    lengths = {lang: len(pool[lang]) for lang in LANGS}
    assert len(set(lengths.values())) == 1, f"languages not index-aligned: {lengths}"
    assert lengths["EN"] >= min_items, f"expected >= {min_items} items, got {lengths['EN']}"
    for lang in LANGS:
        items = pool[lang]
        assert len(set(items)) == len(items), f"{lang} contains duplicate entries"
        assert all(isinstance(x, str) and x.strip() for x in items), f"{lang} has empty entries"
        assert all(len(x) <= 140 for x in items), f"{lang} has an entry over 140 chars"


def test_jokes_pool_expanded_and_aligned():
    # 16 original + 50 new = 66; guard the >= 50 floor from the sprint brief.
    _check_pool(JOKES, 50)


def test_facts_pool_expanded_and_aligned():
    # 12 original + 50 new = 62.
    _check_pool(FACTS, 50)


def test_build_translations_round_trip_jokes():
    # Any item must resolve to all 4 ISO-coded languages by shared index.
    idx = 20
    tr = _build_translations(JOKES["RU"][idx], JOKES, "RU")
    assert set(tr.keys()) == set(_LANG_NORM.values()), tr
    assert tr["ru"] == JOKES["RU"][idx]
    assert tr["en"] == JOKES["EN"][idx]
    assert tr["de"] == JOKES["DE"][idx]
    assert tr["uk"] == JOKES["UA"][idx]


def test_build_translations_round_trip_new_fact():
    # A brand-new (appended) tip must also resolve across all languages.
    idx = len(FACTS["EN"]) - 1
    tr = _build_translations(FACTS["DE"][idx], FACTS, "DE")
    assert tr["en"] == FACTS["EN"][idx]
    assert tr["uk"] == FACTS["UA"][idx]
