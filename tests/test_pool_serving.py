"""No-repeat serving, the 2-month reset, daily caps and the compact seen row."""
from __future__ import annotations

import random
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.data.pool import BUCKET_ITEMS
from app.data.pool.model import L, U
from app.main import app
from app.services import content_tracker, seen_store
from app.services.pool_picker import RESET_AFTER_DAYS, pick_item, pick_variant
from app.services.seen_store import Bucket, SeenState

client = TestClient(app)
KEY = {"x-brain-api-key": "changeme_shared_secret"}
DAY = date(2026, 11, 1)

ITEMS = [U(f"I{i}", f"en{i}", f"de{i}", f"ru{i}", f"uk{i}") for i in range(10)]


# ── picking ──────────────────────────────────────────────────────────────────

def test_unique_until_the_bucket_is_exhausted():
    b, rng = Bucket(), random.Random(1)
    picks = [pick_item(b, ITEMS, "en", DAY, rng) for _ in range(10)]
    assert sorted(picks) == list(range(10))


def test_exhausted_repeats_avoid_recent_and_do_not_reset_early():
    b, rng = Bucket(), random.Random(2)
    first = [pick_item(b, ITEMS, "en", DAY, rng) for _ in range(10)]
    later = DAY + timedelta(days=RESET_AFTER_DAYS - 1)
    for _ in range(20):
        recent = list(b.recent)
        choice = pick_item(b, ITEMS, "en", later, rng)
        assert choice not in recent
        assert all(b.seen(i) for i in range(10)), "no reset before 60 days"
    assert first


def test_reset_only_after_two_months_and_only_when_exhausted():
    b, rng = Bucket(), random.Random(3)
    for _ in range(9):
        pick_item(b, ITEMS, "en", DAY, rng)
    # 70 days later but one item still unseen: serve it, no reset.
    late = DAY + timedelta(days=70)
    remaining = next(i for i in range(10) if not b.seen(i))
    assert pick_item(b, ITEMS, "en", late, rng) == remaining
    # Now exhausted and the pass is ≥ 60 days old → a fresh pass of 10 unique.
    picks = [pick_item(b, ITEMS, "en", late, rng) for _ in range(10)]
    assert sorted(picks) == list(range(10))


def test_items_added_later_are_served_first():
    b, rng = Bucket(), random.Random(4)
    for _ in range(10):
        pick_item(b, ITEMS, "en", DAY, rng)
    grown = ITEMS + [U("NEW", "new", "neu", "новый", "новий")]
    assert pick_item(b, grown, "en", DAY, rng) == 10


def test_language_locked_items_only_in_their_language():
    items = ITEMS[:2] + [L("DE-only", "de", "Wortspiel")]
    for lang in ("en", "ru", "uk"):
        b = Bucket()
        picks = {pick_item(b, items, lang, DAY) for _ in range(6)}
        assert 2 not in picks
    b = Bucket()
    assert 2 in {pick_item(b, items, "de", DAY) for _ in range(3)}


def test_seen_is_shared_across_languages():
    b, rng = Bucket(), random.Random(5)
    picks = [pick_item(b, ITEMS, lang, DAY, rng) for lang in ("en", "de", "ru", "uk") * 2 + ("en", "de")]
    assert sorted(picks) == list(range(10))


def test_variant_recency():
    recent: list[int] = []
    variants = ITEMS[:4]
    out = [pick_variant(recent, variants, "en", lambda v: v.tr["en"], random.Random(i)) for i in range(12)]
    assert all(len(set(out[i:i + 4])) == 4 for i in range(len(out) - 3))


# ── the compact row ──────────────────────────────────────────────────────────

def test_seen_row_round_trips_and_stays_small_at_full_target_size():
    state = SeenState()
    sizes = {"jokes": 220, "facts": 180, "tips": 90, "exits": 30, "quota": 8, "encouragements": 15}
    for name, n in sizes.items():
        b = state.bucket(name)
        for i in range(n):
            b.mark(i)
        b.cycle_day, b.recent = 700, [n - 1, n - 2, n - 3]
    for t in seen_store.MESSAGE_TYPES:
        state.messages[t] = [7, 3, 1]
    blob = state.encode()
    assert len(blob) <= 300, len(blob)
    back = SeenState.decode(blob)
    assert back.encode() == blob
    assert all(back.bucket("facts").seen(i) for i in range(180))


def test_unreadable_or_short_rows_start_fresh():
    assert SeenState.decode(b"\x01\xff").encode() == SeenState().encode()
    assert SeenState.decode(None).buckets == {}


# ── serving through the tracker ──────────────────────────────────────────────

def test_daily_caps_then_quota_lines(monkeypatch):
    jokes = [client.get("/v1/tamagotchi/content", params={"user_id": 7, "category": "joke", "language": "RU"}, headers=KEY).json() for _ in range(3)]
    assert [j["type"] for j in jokes] == ["JOKE", "JOKE", "QUOTA"]
    assert jokes[0]["content"] != jokes[1]["content"]
    assert set(jokes[0]["all_translations"]) <= {"en", "de", "ru", "uk"}
    facts = [client.get("/v1/tamagotchi/content", params={"user_id": 7, "category": "fact", "language": "DE"}, headers=KEY).json() for _ in range(3)]
    assert [f["type"] for f in facts] == ["FACT", "FACT", "QUOTA"]
    exits = [client.get("/v1/tamagotchi/content", params={"user_id": 7, "category": "exit", "language": "UA"}, headers=KEY).json() for _ in range(5)]
    assert all(e["type"] == "EXIT" and e["content"] for e in exits), "exit lines have no cap"


def test_next_day_resets_the_caps(monkeypatch):
    for _ in range(2):
        content_tracker.serve_item(8, "jokes", "EN")
    assert content_tracker.serve_item(8, "jokes", "EN") == (None, True)

    class Tomorrow(date):
        @classmethod
        def today(cls):
            return date.today() + timedelta(days=1)

    monkeypatch.setattr(content_tracker, "date_type", Tomorrow)
    item, capped = content_tracker.serve_item(8, "jokes", "EN")
    assert item is not None and not capped


def test_tip_at_most_once_a_day_in_the_ambient_channel():
    types = [client.get("/v1/tamagotchi/next-action", params={"user_id": 9, "language": "EN"}, headers=KEY).json()["type"] for _ in range(6)]
    assert types[0] == "GREETING"
    assert types.count("TIP") == 1
    assert "JOKE" not in types and "FACT" not in types


def test_daily_row_holds_no_item_text():
    for cat in ("joke", "fact", "exit"):
        client.get("/v1/tamagotchi/content", params={"user_id": 10, "category": cat, "language": "EN"}, headers=KEY)
    row = content_tracker._load_user(10)
    assert set(row) <= set(content_tracker._DAILY_KEYS)
    texts = {t for items in BUCKET_ITEMS.values() for it in items for t in it.tr.values()}
    assert not any(isinstance(v, str) and v in texts for v in row.values())


def test_legacy_seen_texts_are_imported_then_dropped():
    legacy_joke = BUCKET_ITEMS["jokes"][0].tr["ru"]
    content_tracker._save_user(11, {"date": "2020-01-01", "seen_jokes": [legacy_joke]})
    content_tracker._file_save(11, {"date": "2020-01-01", "seen_jokes": [legacy_joke]})  # raw legacy row
    content_tracker.serve_item(11, "facts", "EN")
    with seen_store.session(11) as state:
        assert state.bucket("jokes").seen(0)
    assert "seen_jokes" not in content_tracker._load_user(11)
