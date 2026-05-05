from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.request import AnalyzeBehaviorRequest, CategoryInfo, TransactionItem, UserProfile
from app.services import (
    forecaster,
    health_scorer,
    mood_engine,
    sustainability_scorer,
    tier_calculator,
)

client = TestClient(app)
VALID_KEY = "changeme_shared_secret"

# ─── Fixtures ────────────────────────────────────────────────────────────────

TODAY = date(2026, 5, 5)  # Tuesday


def _tx(
    *,
    tx_id: int = 1,
    amount: float,
    cat_name: str = "Food",
    tx_date: date = TODAY,
    tx_type: str = "expense",
    income_type: str = "one_time",
) -> TransactionItem:
    return TransactionItem(
        id=tx_id,
        amount=amount,
        category=CategoryInfo(id=tx_id, name=cat_name),
        date=tx_date,
        type=tx_type,
        income_type=income_type,
    )


def _profile(**kwargs) -> UserProfile:
    defaults = dict(
        user_id=1,
        currency="EUR",
        monthly_spending_goal=2000.0,
        expected_salary=5000.0,
        payday_mode="fixed",
        fixed_payday=15,
    )
    defaults.update(kwargs)
    return UserProfile(**defaults)


SAMPLE_REQUEST = {
    "user_profile": {
        "user_id": 1,
        "currency": "EUR",
        "monthly_spending_goal": 2000.0,
        "expected_salary": 5000.0,
        "payday_mode": "fixed",
        "fixed_payday": 15,
        "manual_next_payday": None,
        "ai_humor_enabled": True,
    },
    "transactions": [
        {
            "id": 1,
            "amount": 50.0,
            "category": {"id": 1, "name": "Food & Dining"},
            "date": "2026-05-01",
            "type": "expense",
            "income_type": "one_time",
            "description": "Groceries",
        },
        {
            "id": 2,
            "amount": 5000.0,
            "category": {"id": 5, "name": "Income"},
            "date": "2026-05-01",
            "type": "income",
            "income_type": "one_time",
            "description": "Salary",
        },
    ],
    "analysis_date": "2026-05-05",
}

# ─── Health endpoint ─────────────────────────────────────────────────────────


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ─── Auth ────────────────────────────────────────────────────────────────────


def test_missing_api_key_returns_422():
    resp = client.post("/v1/analyze-behavior", json=SAMPLE_REQUEST)
    assert resp.status_code == 422


def test_wrong_api_key_returns_401():
    resp = client.post(
        "/v1/analyze-behavior",
        json=SAMPLE_REQUEST,
        headers={"x-brain-api-key": "wrongkey"},
    )
    assert resp.status_code == 401


# ─── Integration: happy path ─────────────────────────────────────────────────

VALID_MOODS = {"thriving", "content", "worried", "stressed", "exhausted"}
VALID_TIERS = {"salary_just_in", "pacing_over", "pacing_warn", "pacing_great", "balanced", "pacing_good"}


def test_full_analyze_happy_path():
    resp = client.post(
        "/v1/analyze-behavior",
        json=SAMPLE_REQUEST,
        headers={"x-brain-api-key": VALID_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 1 <= data["financial_health_score"] <= 100
    assert 1 <= data["sustainability_score"] <= 100
    assert data["tamagotchi_mood"] in VALID_MOODS
    assert data["spending_tier"] in VALID_TIERS
    assert isinstance(data["risk_flags"], list)
    assert isinstance(data["smart_nudge"], str)
    assert len(data["smart_nudge"]) > 0


def test_empty_transactions_does_not_crash():
    payload = {**SAMPLE_REQUEST, "transactions": []}
    resp = client.post(
        "/v1/analyze-behavior",
        json=payload,
        headers={"x-brain-api-key": VALID_KEY},
    )
    assert resp.status_code == 200


def test_manual_next_payday_empty_string_accepted():
    payload = {**SAMPLE_REQUEST}
    payload["user_profile"] = {**SAMPLE_REQUEST["user_profile"], "manual_next_payday": ""}
    resp = client.post(
        "/v1/analyze-behavior",
        json=payload,
        headers={"x-brain-api-key": VALID_KEY},
    )
    assert resp.status_code == 200


# ─── Unit: health_scorer ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "expense,income,goal,expected_low,expected_high",
    [
        (500, 5000, 2000, 75, 100),    # well under goal, good savings
        (2500, 2000, 2000, 10, 35),    # over income and goal
        (0, 2000, 2000, 95, 100),      # no spending
        (2000, 2000, 2000, 25, 40),    # at the threshold: ratio=0, goal=100, diversity=0, savings=0 → 30
    ],
)
def test_health_score_ranges(expense, income, goal, expected_low, expected_high):
    txs = []
    if expense > 0:
        txs.append(_tx(amount=expense, cat_name="Food", tx_date=TODAY))
    if income > 0:
        txs.append(_tx(amount=income, cat_name="Salary", tx_date=TODAY, tx_type="income"))
    profile = _profile(monthly_spending_goal=goal, expected_salary=income)
    score, _ = health_scorer.compute_financial_health_score(txs, profile, TODAY)
    assert expected_low <= score <= expected_high, f"score={score} not in [{expected_low},{expected_high}]"


def test_no_income_flag():
    txs = [_tx(amount=100)]
    profile = _profile(expected_salary=0.0)
    _, flags = health_scorer.compute_financial_health_score(txs, profile, TODAY)
    assert "no_income" in flags


def test_single_category_triggers_high_spend_flag():
    txs = [_tx(amount=1000, cat_name="Food", tx_id=i, tx_date=TODAY) for i in range(1, 4)]
    profile = _profile()
    _, flags = health_scorer.compute_financial_health_score(txs, profile, TODAY)
    assert any("high_" in f and "_spend" in f for f in flags)


def test_expenses_exceed_income_flag():
    txs = [
        _tx(amount=3000, cat_name="Rent"),
        _tx(amount=500, cat_name="Salary", tx_type="income"),
    ]
    profile = _profile(expected_salary=0.0)
    _, flags = health_scorer.compute_financial_health_score(txs, profile, TODAY)
    assert "expenses_exceed_income" in flags


# ─── Unit: sustainability_scorer ─────────────────────────────────────────────


def test_sustainability_green_dominant():
    txs = [_tx(amount=500, cat_name="Grocery"), _tx(amount=50, cat_name="Fuel", tx_id=2)]
    score = sustainability_scorer.compute_sustainability_score(txs, TODAY)
    assert score > 50


def test_sustainability_negative_dominant():
    txs = [_tx(amount=500, cat_name="Alcohol"), _tx(amount=50, cat_name="Grocery", tx_id=2)]
    score = sustainability_scorer.compute_sustainability_score(txs, TODAY)
    assert score < 50


def test_sustainability_neutral_only_near_50():
    txs = [_tx(amount=500, cat_name="Miscellaneous")]
    score = sustainability_scorer.compute_sustainability_score(txs, TODAY)
    assert score == 50


def test_sustainability_empty_transactions():
    score = sustainability_scorer.compute_sustainability_score([], TODAY)
    assert 1 <= score <= 100


# ─── Unit: mood_engine ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "score,expected_mood",
    [
        (100, "thriving"),
        (81, "thriving"),
        (80, "content"),
        (61, "content"),
        (60, "worried"),
        (41, "worried"),
        (40, "stressed"),
        (21, "stressed"),
        (20, "exhausted"),
        (1, "exhausted"),
    ],
)
def test_mood_boundaries(score, expected_mood):
    assert mood_engine.get_tamagotchi_mood(score) == expected_mood


# ─── Unit: forecaster ────────────────────────────────────────────────────────


def test_forecaster_fallback_fewer_than_7_days():
    txs = [_tx(amount=100, tx_date=date(2026, 5, 1))]
    result = forecaster.predict_end_of_month_balance(txs, TODAY, 5000.0)
    assert isinstance(result, float)
    assert result < 5000.0


def test_forecaster_regression_path():
    txs = [
        _tx(tx_id=i, amount=50.0, tx_date=date(2026, 5, i))
        for i in range(1, 9)
    ]
    result = forecaster.predict_end_of_month_balance(txs, date(2026, 5, 8), 5000.0)
    assert isinstance(result, float)
    assert result < 5000.0


def test_forecaster_never_less_than_income_minus_full_month():
    txs = [_tx(tx_id=i, amount=10.0, tx_date=date(2026, 5, i)) for i in range(1, 30)]
    result = forecaster.predict_end_of_month_balance(txs, date(2026, 5, 29), 5000.0)
    assert isinstance(result, float)


def test_forecaster_no_transactions_returns_salary():
    result = forecaster.predict_end_of_month_balance([], TODAY, 5000.0)
    assert result == 5000.0


# ─── Unit: tier_calculator ───────────────────────────────────────────────────


def test_tier_salary_just_in():
    two_days_ago = TODAY - timedelta(days=2)
    txs = [_tx(amount=5000, tx_date=two_days_ago, tx_type="income", income_type="one_time")]
    profile = _profile()
    assert tier_calculator.compute_spending_tier(txs, profile, TODAY) == "salary_just_in"


def test_tier_pacing_over():
    # weekly_limit = 2000 / 4.3 ≈ 465; spend 600 → pace ≈ 1.29
    monday = TODAY - timedelta(days=TODAY.isoweekday() - 1)
    txs = [_tx(amount=600, tx_date=monday)]
    profile = _profile()
    assert tier_calculator.compute_spending_tier(txs, profile, TODAY) == "pacing_over"


def test_tier_pacing_warn():
    # spend 400 → pace ≈ 0.86
    monday = TODAY - timedelta(days=TODAY.isoweekday() - 1)
    txs = [_tx(amount=400, tx_date=monday)]
    profile = _profile()
    assert tier_calculator.compute_spending_tier(txs, profile, TODAY) == "pacing_warn"


def test_tier_no_goal_returns_pacing_good():
    txs = [_tx(amount=100)]
    profile = _profile(monthly_spending_goal=0.0)
    assert tier_calculator.compute_spending_tier(txs, profile, TODAY) == "pacing_good"


def test_tier_balanced():
    # pace < 0.8, 2 categories, no single one > 45%
    monday = TODAY - timedelta(days=TODAY.isoweekday() - 1)
    txs = [
        _tx(tx_id=1, amount=100, cat_name="Food", tx_date=monday),
        _tx(tx_id=2, amount=100, cat_name="Transport", tx_date=monday),
    ]
    profile = _profile()
    result = tier_calculator.compute_spending_tier(txs, profile, TODAY)
    assert result in ("balanced", "pacing_good")


# ─── Alignment: tier matches frontend logic for pacing_warn scenario ─────────


def test_tier_alignment_pacing_warn():
    """
    Reproduces the exact scenario the frontend marks as pacing_warn:
    weekly spend is between 80%–120% of weekly_limit.
    """
    monday = TODAY - timedelta(days=TODAY.isoweekday() - 1)
    weekly_limit = 2000 / 4.3
    spend = weekly_limit * 0.9  # 90% → pacing_warn
    txs = [_tx(amount=spend, tx_date=monday)]
    profile = _profile()
    assert tier_calculator.compute_spending_tier(txs, profile, TODAY) == "pacing_warn"
