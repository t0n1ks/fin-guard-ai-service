"""Integrity and safety guards for the companion content pool.

The pool is append-only data (app/data/pool): every item has a stable id and
position, universal items exist in all four languages, language-locked items
in exactly one, and nothing shaming or offensive may ship in any language.
"""
from __future__ import annotations

import re
import string

import pytest

from app.data import content as greetings
from app.data.pool import BUCKET_ITEMS, MESSAGES
from app.data.pool.model import LANGS, Item
from app.services import seen_store
from app.services.locale_format import format_slots

DISPLAY_CAP = 140

# Floors for the current batch; raised as the pool fills (targets: jokes 180,
# facts 180, tips 90, exits 30, nudges 20, message variants ~100).
FLOORS = {"jokes": 200, "facts": 15, "tips": 55, "exits": 30, "quota": 8, "encouragements": 15}

# Numbers Go sends per message type (see app/data/pool/messages.py).
MESSAGE_SLOTS = {
    "overspent": {"over", "remaining", "days_left"},
    "big_expense": {"amount", "ratio", "category", "remaining", "days_left", "daily"},
    "savings_deposit": {"amount", "saved_total"},
    "income": {"amount"},
    "pace_warn": {"spent_pct", "elapsed_pct", "remaining", "days_left", "daily"},
    "pace_over": {"spent_pct", "elapsed_pct", "remaining", "days_left", "daily"},
    "pace_recovered": {"spent_pct", "elapsed_pct", "remaining", "days_left", "daily"},
    "payday_tomorrow": {"remaining", "days_left", "daily"},
    "last_days": {"remaining", "days_left", "daily"},
    "week_checkin": {"week", "spent", "remaining", "days_left", "daily", "forecast_end"},
    "weekday_heads_up": {"weekday", "remaining", "days_left", "daily"},
    "quest_ask": set(),
}
SAMPLE_SLOTS = {
    "over": 12.5, "remaining": 212.0, "days_left": 14, "daily": 15.14, "amount": 80.0, "ratio": 2.5,
    "category": "Food", "saved_total": 340.0, "spent_pct": 62, "elapsed_pct": 40, "week": 2,
    "spent": 238.0, "forecast_end": -40.5, "weekday": 5, "calibrating": True,
}

# Shaming words (research: shame makes people avoid their finances).
SHAME = {
    "en": r"\b(fail|failed|failure|bad|shame|shameful|terrible|guilty|wasted|irresponsible|stupid|lazy)\b",
    "de": r"(versag|schlecht|schäm|schande|schrecklich|schuldig|verschwend|dumm|faul\b)",  # „Schuld“ alone = debt
    "ru": r"(провал|плох|стыд|позор|ужасн|винова|растратил|безответствен|глуп|лентя)",
    "uk": r"(провал|погано|поганий|сором(?!'я)|ганьб|жахлив|винн|розтратив|безвідповідальн|дурн|ледач)",  # not сором'язливий (shy)
}
# Slurs and gross insults (stems). Nothing like this may ever ship.
SLURS = {
    "en": r"(nigg|\bfag|retard|tranny|\bkike|\bspic\b|chink|wetback|\bslut|whore|\bcunt|\bdyke)",
    "de": r"(neger|schwuchtel|\bspast|kanake|fotze|nutte|zigeuner|\bschlampe)",
    "ru": r"(пидор|пидар|хохол|\bжид|чурк|ниггер|\bшлюх|чучмек|даун\b|\bхач\b)",
    "uk": r"(підор|\bжид|чурк|ніггер|\bшльондр|\bповія|кацап|\bхохол|москал)",
}


def all_items() -> list[tuple[str, Item]]:
    out = [(name, it) for name, items in BUCKET_ITEMS.items() for it in items]
    out += [(f"msg:{t}", it) for t, items in MESSAGES.items() for it in items]
    return out


def all_texts() -> list[tuple[str, str, str]]:
    """(where, language, text) for every shipped line, greetings included."""
    out = [(f"{where}:{it.id}", lang, text) for where, it in all_items() for lang, text in it.tr.items()]
    for name in ("GREETINGS", "CHEERFUL_GREETINGS", "GRUMPY_GREETINGS"):
        pool = getattr(greetings, name)
        for code, entries in pool.items():
            lang = {"EN": "en", "DE": "de", "RU": "ru", "UA": "uk"}[code]
            texts = [t for seg in entries.values() for t in seg] if isinstance(entries, dict) else entries
            out += [(name, lang, t) for t in texts]
    return out


# ── structure ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bucket", list(BUCKET_ITEMS))
def test_bucket_meets_its_floor(bucket):
    live = [it for it in BUCKET_ITEMS[bucket] if not it.retired]
    assert len(live) >= FLOORS[bucket]


def test_ids_are_unique_and_positions_fit_the_seen_row():
    ids = [it.id for _, it in all_items()]
    assert len(ids) == len(set(ids)), "duplicate ids"
    assert all(len(items) < 65536 for items in BUCKET_ITEMS.values())
    assert all(len(items) < 256 for items in MESSAGES.values())
    assert list(BUCKET_ITEMS) == list(seen_store.BUCKETS)
    assert set(MESSAGES) == set(seen_store.MESSAGE_TYPES)


def test_universal_items_exist_in_all_four_languages_and_locked_in_one():
    for where, it in all_items():
        texts = {lang: t for lang, t in it.tr.items() if t and t.strip()}
        if it.only:
            assert set(texts) == {it.only}, f"{where}:{it.id} locked item must exist only in {it.only}"
        else:
            assert set(texts) == set(LANGS), f"{where}:{it.id} is missing {set(LANGS) - set(texts)}"


def test_jokes_reach_the_target_and_every_language_has_locked_extras():
    jokes = [it for it in BUCKET_ITEMS["jokes"] if not it.retired]
    assert sum(1 for it in jokes if not it.only) >= 180
    for lang in LANGS:
        assert sum(1 for it in jokes if it.only == lang) >= 5, lang


@pytest.mark.parametrize("bucket", [b for b in BUCKET_ITEMS])
def test_items_fit_the_bubble_and_do_not_repeat(bucket):
    for lang in LANGS:
        texts = [it.text_in(lang) for it in BUCKET_ITEMS[bucket]]
        texts = [t for t in texts if t]
        assert len(texts) == len(set(texts)), f"{bucket}/{lang} has a duplicate line"
        assert all(len(t) <= DISPLAY_CAP for t in texts), f"{bucket}/{lang} has a line over {DISPLAY_CAP} chars"


def test_message_variants_use_only_the_numbers_go_sends_and_render_everywhere():
    for type_, variants in MESSAGES.items():
        allowed = MESSAGE_SLOTS[type_]
        for v in variants:
            for lang in LANGS:
                text = v.text_in(lang)
                names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
                assert names <= allowed, f"{v.id}/{lang} uses {names - allowed}"
                rendered = text.format_map(format_slots(SAMPLE_SLOTS, "EUR", lang))
                assert "{" not in rendered and "}" not in rendered, f"{v.id}/{lang}"
            assert v.when in (None, "calibrating")


def test_week_one_variants_never_cite_a_projection():
    for v in (v for variants in MESSAGES.values() for v in variants if v.when == "calibrating"):
        assert all("{forecast_end}" not in t for t in v.tr.values()), v.id


def test_every_message_type_has_enough_variants():
    for type_, variants in MESSAGES.items():
        assert len(variants) >= (20 if type_ == "quest_ask" else 8), type_
    assert sum(len(v) for t, v in MESSAGES.items() if t != "quest_ask") >= 90


# ── safety ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", LANGS)
def test_no_shaming_words(lang):
    pattern = re.compile(SHAME[lang], re.IGNORECASE)
    hits = [(w, t) for w, l, t in all_texts() if l == lang and pattern.search(t)]
    assert not hits, hits


@pytest.mark.parametrize("lang", LANGS)
def test_no_slurs(lang):
    pattern = re.compile(SLURS[lang], re.IGNORECASE)
    hits = [(w, t) for w, l, t in all_texts() if l == lang and pattern.search(t)]
    assert not hits, hits


def test_scan_patterns_catch_what_they_should():
    assert re.search(SHAME["en"], "You failed again", re.I)
    assert re.search(SHAME["ru"], "Тебе должно быть стыдно", re.I)
    assert re.search(SLURS["de"], "So ein Spast", re.I)
    assert not re.search(SHAME["de"], "Schulden zuerst abbauen", re.I)
