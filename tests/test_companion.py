from __future__ import annotations

from fastapi.testclient import TestClient

from app.data.pool.model import U
from app.main import app
from app.services.companion_renderer import format_amount, render_message
from app.services.locale_format import format_slots

client = TestClient(app)
VALID_KEY = "changeme_shared_secret"

POOL = {
    "last_days": [
        U("T-1", "{days_left} to go: {remaining} left, about {daily}/day.", "de1 {remaining}", "Осталось: {remaining}, около {daily} в день.", "uk1 {remaining}"),
        U("T-2", "Almost there — {remaining}.", "de2 {remaining}", "ru2 {remaining}", "uk2 {remaining}"),
        U("T-3", "Third — {remaining}.", "de3 {remaining}", "ru3 {remaining}", "uk3 {remaining}"),
    ],
    "week_checkin": [U("T-W", "Week {week}: card says {forecast_end}.", "x {forecast_end}", "x {forecast_end}", "x {forecast_end}")],
    "income": [
        U("T-I1", "Got {amount}.", "de", "ru", "uk"),
        U("T-I2", "First week — {amount}, still learning.", "de", "ru", "uk", when="calibrating"),
    ],
}
SLOTS = {"remaining": 45.0, "days_left": 3, "daily": 15.0}


def test_amounts_are_written_the_way_each_language_writes_them():
    assert format_amount(12.5, "EUR") == "€12.5"
    assert format_amount(-40, "EUR") == "−€40"
    assert format_amount(1234.5, "EUR", "de") == "€1.234,5"
    assert format_amount(1234.5, "EUR", "ru") == "€1 234,5"
    assert format_amount(3, "XYZ") == "XYZ 3"
    slots = format_slots({"ratio": 2.5, "weekday": 5, "spent_pct": 62.0, "calibrating": True}, "EUR", "uk")
    assert slots == {"ratio": "2,5", "weekday": "пʼятниця", "spent_pct": "62"}


def test_render_fills_numbers_in_the_language():
    text = render_message(1, "last_days", "supportive", "ru", SLOTS, "EUR", pool={"last_days": POOL["last_days"][:1]})
    assert text == "Осталось: €45, около €15 в день."


def test_render_avoids_the_last_variants_for_a_type():
    seen = [render_message(2, "last_days", "supportive", "en", SLOTS, "EUR", pool=POOL) for _ in range(9)]
    assert all(a != b for a, b in zip(seen, seen[1:]))
    # With 3 variants, the window avoids the last 2: each run of 3 is all different.
    assert all(len(set(seen[i:i + 3])) == 3 for i in range(len(seen) - 2))


def test_render_skips_variants_missing_a_number():
    # Week 1: Go sends no forecast_end, so a template citing it is never used.
    assert render_message(3, "week_checkin", "supportive", "en", {"week": 2}, "EUR", pool=POOL) is None


def test_calibrating_variants_only_in_the_first_week():
    texts = {render_message(4, "income", "supportive", "en", {"amount": 5}, "EUR", pool=POOL) for _ in range(6)}
    assert texts == {"Got €5."}
    texts = {render_message(5, "income", "supportive", "en", {"amount": 5, "calibrating": True}, "EUR", pool=POOL) for _ in range(12)}
    assert "First week — €5, still learning." in texts


def test_render_none_without_variants():
    assert render_message(6, "quest_ask", "playful", "de", {}, "EUR", pool=POOL) is None


def test_endpoint_words_every_language_from_the_pool():
    for lang in ("en", "de", "ru", "uk"):
        resp = client.post(
            "/v1/companion/render",
            json={"user_id": 1, "type": "last_days", "language": lang, "slots": SLOTS, "currency": "EUR"},
            headers={"x-brain-api-key": VALID_KEY},
        )
        assert resp.status_code == 200
        text = resp.json()["text"]
        assert text and "{" not in text and "€" in text  # some variants cite only the daily amount


def test_endpoint_requires_the_api_key():
    resp = client.post("/v1/companion/render", json={"user_id": 1, "type": "last_days"})
    assert resp.status_code == 401
