from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import companion_renderer
from app.services.companion_renderer import format_amount, render_message

client = TestClient(app)
VALID_KEY = "changeme_shared_secret"

POOL = {
    "last_days": {
        "en": ["{days_left} days to go: {remaining} left, about {daily}/day.", "Almost there — {remaining} for {days_left} days."],
        "ru": ["Осталось {days_left} дня: {remaining}, около {daily} в день."],
    },
    "week_checkin": {"en": ["Week {week}: {remaining} left. Card says {forecast_end}."]},
}
SLOTS = {"remaining": 45.0, "days_left": 3, "daily": 15.0}


def test_format_amount_uses_currency_and_true_minus():
    assert format_amount(12.5, "EUR") == "€12.50"
    assert format_amount(-40, "EUR") == "−€40.00"
    assert format_amount(3, "XYZ") == "XYZ 3.00"


def test_render_fills_numbers_in_the_language():
    text = render_message(1, "last_days", "supportive", "ru", SLOTS, "EUR", pool=POOL)
    assert text == "Осталось 3 дня: €45.00, около €15.00 в день."


def test_render_never_repeats_the_last_variant():
    companion_renderer._recent.clear()
    seen = [render_message(2, "last_days", "supportive", "en", SLOTS, "EUR", pool=POOL) for _ in range(6)]
    assert all(a != b for a, b in zip(seen, seen[1:]))


def test_render_skips_variants_missing_a_number():
    # Week 1: Go sends no forecast_end, so a template citing it is never used.
    assert render_message(3, "week_checkin", "supportive", "en", {"week": 2, "remaining": 10}, "EUR", pool=POOL) is None


def test_render_none_without_variants():
    assert render_message(4, "quest_ask", "playful", "de", {}, "EUR", pool=POOL) is None


def test_endpoint_returns_null_text_until_stage_d():
    resp = client.post(
        "/v1/companion/render",
        json={"user_id": 1, "type": "last_days", "language": "uk", "slots": SLOTS, "currency": "EUR"},
        headers={"x-brain-api-key": VALID_KEY},
    )
    assert resp.status_code == 200
    assert resp.json() == {"text": None}


def test_endpoint_requires_the_api_key():
    resp = client.post("/v1/companion/render", json={"user_id": 1, "type": "last_days"})
    assert resp.status_code == 401
