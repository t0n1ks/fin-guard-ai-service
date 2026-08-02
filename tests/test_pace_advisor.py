from __future__ import annotations

from datetime import date

import pytest

from app.models.request import (
    CategoryInfo,
    SalaryCycleInfo,
    TransactionItem,
    UserProfile,
)
from app.services import nudge_generator, pace_advisor, tier_calculator

# ─── pace_advisor.evaluate_pace: tiers & boundaries ──────────────────────────


def test_no_allowance_yields_no_verdict():
    v = pace_advisor.evaluate_pace(0.0, 20.0, 3, 4)
    assert v.tier == pace_advisor.TIER_NONE
    assert not v.has_verdict


def test_fresh_week_zero_elapsed_is_neutral_no_scary_pct():
    # Day 0 of the week — must never emit a pace percentage.
    v = pace_advisor.evaluate_pace(76.78, 0.0, 0, 7)
    assert v.tier == pace_advisor.TIER_FRESH
    assert v.pct_over == 0


def test_fresh_week_nothing_spent_is_neutral():
    v = pace_advisor.evaluate_pace(76.78, 0.0, 3, 4)
    assert v.tier == pace_advisor.TIER_FRESH


def test_regression_under_budget_never_reads_as_over():
    # The exact screenshot scenario: allowance €76.78, spent €36.58, midweek.
    # Must NOT be pacing_over and pct_over MUST be 0.
    v = pace_advisor.evaluate_pace(76.78, 36.58, 3, 4)
    assert v.tier != pace_advisor.TIER_OVER
    assert v.pct_over == 0
    assert v.pct_used == 48  # 36.58 / 76.78 → 47.6% → 48


def test_late_week_low_spend_invites_a_treat():
    # 2 days left, only 10% used → encouraging "treat yourself".
    v = pace_advisor.evaluate_pace(100.0, 10.0, 5, 2)
    assert v.tier == pace_advisor.TIER_GREAT
    assert v.pct_over == 0


def test_remarkably_lean_past_midweek_is_great():
    # Well under an even pace and past midweek, even with days still left.
    v = pace_advisor.evaluate_pace(100.0, 15.0, 4, 3)
    assert v.tier == pace_advisor.TIER_GREAT


def test_on_even_pace_is_good():
    # Half the allowance used at the halfway point → ratio ≈ 1.0.
    v = pace_advisor.evaluate_pace(100.0, 50.0, 4, 3)
    assert v.tier == pace_advisor.TIER_GOOD


def test_slightly_over_pace_with_time_left_is_gentle_warn_not_over():
    # Ahead of pace (ratio ≈ 1.6) but still UNDER the allowance → warn, not over.
    v = pace_advisor.evaluate_pace(100.0, 45.0, 2, 5)
    assert v.tier == pace_advisor.TIER_WARN
    assert v.pct_over == 0  # under budget → never an "over the limit" number


def test_spent_over_allowance_is_honest_over_with_true_overage():
    # 133 spent on a 100 allowance → pacing_over, pct_over = 33.
    v = pace_advisor.evaluate_pace(100.0, 133.0, 4, 3)
    assert v.tier == pace_advisor.TIER_OVER
    assert v.pct_used == 133
    assert v.pct_over == 33


def test_pct_over_only_positive_when_truly_over():
    for spent in (0.0, 10.0, 50.0, 99.9, 100.0):
        v = pace_advisor.evaluate_pace(100.0, spent, 4, 3)
        assert v.pct_over == 0, f"spent={spent} should not read as over"
    assert pace_advisor.evaluate_pace(100.0, 120.0, 4, 3).pct_over == 20


# ─── Integration through tier_calculator & nudge_generator ───────────────────

FIXED_CAT = 99
CYCLE_START = "2026-05-01T12:00:00+00:00"
NEXT_PAYDAY = "2026-05-31T12:00:00+00:00"


def _cycle(**kwargs) -> SalaryCycleInfo:
    defaults = dict(
        total_income=2000.0,
        cycle_active=True,
        weekly_allowance=76.78,
        spent_this_week=36.58,
        days_elapsed_in_week=3,
        days_remaining_in_week=4,
        days_until_next_payout=20,
        cycle_start_at=CYCLE_START,
        next_payday_at=NEXT_PAYDAY,
        fixed_exp_category_id=FIXED_CAT,
    )
    defaults.update(kwargs)
    return SalaryCycleInfo(**defaults)


def _profile(**kwargs) -> UserProfile:
    defaults = dict(user_id=1, currency="EUR", monthly_spending_goal=300.0, language="RU")
    defaults.update(kwargs)
    return UserProfile(**defaults)


def _var_tx(amount: float, d: date) -> TransactionItem:
    return TransactionItem(
        id=1, amount=amount, category=CategoryInfo(id=1, name="Food"),
        date=d, type="expense", income_type="one_time",
    )


def test_tier_uses_authoritative_cycle_not_monthly_goal():
    # monthly_spending_goal (300 → weekly ≈70) is intentionally small so the OLD
    # formula would scream "over"; the authoritative allowance keeps it calm.
    cycle = _cycle()
    txs = [_var_tx(36.58, date(2026, 5, 4))]
    tier = tier_calculator.compute_spending_tier(txs, _profile(), date(2026, 5, 4), salary_cycle=cycle)
    assert tier not in ("pacing_over",)


def test_nudge_never_shows_over_percentage_while_under_budget():
    cycle = _cycle(spent_this_week=36.58, weekly_allowance=76.78)
    profile = _profile(language="RU")
    txs = [_var_tx(36.58, date(2026, 5, 4))]
    nudge = nudge_generator.generate_nudge(
        tier="pacing_warn", risk_flags=[], profile=profile, transactions=txs,
        analysis_date=date(2026, 5, 4), predicted_balance=100.0, salary_cycle=cycle,
    )
    # No "over budget" percentage phrasing when under the allowance.
    assert "%" not in nudge or "перерасход" not in nudge.lower()


def test_nudge_over_budget_shows_true_overage():
    cycle = _cycle(spent_this_week=133.0, weekly_allowance=100.0, days_elapsed_in_week=4)
    profile = _profile(language="EN")
    txs = [_var_tx(133.0, date(2026, 5, 5))]
    nudge = nudge_generator.generate_nudge(
        tier="pacing_over", risk_flags=[], profile=profile, transactions=txs,
        analysis_date=date(2026, 5, 5), predicted_balance=-50.0, salary_cycle=cycle,
    )
    assert "33%" in nudge


def test_inactive_cycle_falls_back_to_legacy():
    cycle = _cycle(cycle_active=False)
    txs = [_var_tx(10.0, date(2026, 5, 4))]
    # Should not raise and should still return a valid tier from the legacy path.
    tier = tier_calculator.compute_spending_tier(txs, _profile(), date(2026, 5, 4), salary_cycle=cycle)
    assert isinstance(tier, str) and tier
