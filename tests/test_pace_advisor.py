from __future__ import annotations

from datetime import date

import pytest

from app.models.request import (
    BudgetWindowInfo,
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


def test_inactive_cycle_falls_back_gracefully():
    cycle = _cycle(cycle_active=False)
    txs = [_var_tx(10.0, date(2026, 5, 4))]
    # No authoritative window at all → a valid, percentage-free tier, never a
    # verdict invented from monthly_spending_goal / 4.3.
    tier = tier_calculator.compute_spending_tier(txs, _profile(), date(2026, 5, 4), salary_cycle=cycle)
    assert tier in ("pacing_good", "balanced")


# ─── No-cycle (monthly-goal) users: same machinery, same guarantees ──────────


def _window(**kwargs) -> BudgetWindowInfo:
    """Authoritative monthly budget window from Go's computeBudgetWindow."""
    defaults = dict(
        has_goal=True,
        monthly_budget=1000.0,
        spent_this_window=200.0,
        weekly_allowance=76.78,
        spent_this_week=36.58,
        days_elapsed_in_week=3,
        days_remaining_in_week=4,
        days_remaining_in_window=20,
    )
    defaults.update(kwargs)
    return BudgetWindowInfo(**defaults)


def test_no_cycle_uses_budget_window_not_monthly_goal():
    # monthly_spending_goal (300 → old weekly ≈70) would have screamed "over" for
    # a 100 spend; the authoritative window (allowance 300) keeps it calm.
    window = _window(weekly_allowance=300.0, spent_this_week=100.0, days_elapsed_in_week=3, days_remaining_in_week=4)
    txs = [_var_tx(100.0, date(2026, 5, 4))]
    tier = tier_calculator.compute_spending_tier(
        txs, _profile(), date(2026, 5, 4), budget_window=window
    )
    assert tier != "pacing_over"


def test_no_cycle_regression_under_budget_never_reads_as_over():
    # The screenshot scenario for a no-cycle user: €76.78 allowance, €36.58 spent.
    v = pace_advisor.resolve_pace(None, _window())
    assert v.tier != pace_advisor.TIER_OVER
    assert v.pct_over == 0
    assert v.pct_used == 48


def test_no_cycle_over_allowance_is_honest_over():
    v = pace_advisor.resolve_pace(None, _window(weekly_allowance=100.0, spent_this_week=133.0, days_elapsed_in_week=4, days_remaining_in_week=3))
    assert v.tier == pace_advisor.TIER_OVER
    assert v.pct_over == 33


@pytest.mark.parametrize(
    "allowance,spent,elapsed,remaining,expected",
    [
        (100.0, 0.0, 0, 7, pace_advisor.TIER_FRESH),   # week just started
        (100.0, 0.0, 3, 4, pace_advisor.TIER_FRESH),   # nothing spent yet
        (100.0, 50.0, 4, 3, pace_advisor.TIER_GOOD),   # on an even pace
        (100.0, 45.0, 2, 5, pace_advisor.TIER_WARN),   # ahead of pace, still under
        (100.0, 10.0, 5, 2, pace_advisor.TIER_GREAT),  # lean, home stretch
        (100.0, 120.0, 4, 3, pace_advisor.TIER_OVER),  # truly over
    ],
)
def test_no_cycle_tier_boundaries(allowance, spent, elapsed, remaining, expected):
    v = pace_advisor.resolve_pace(
        None,
        _window(
            weekly_allowance=allowance, spent_this_week=spent,
            days_elapsed_in_week=elapsed, days_remaining_in_week=remaining,
        ),
    )
    assert v.tier == expected


@pytest.mark.parametrize("spent", [0.0, 10.0, 50.0, 99.9, 100.0])
def test_no_cycle_pct_over_only_positive_when_truly_over(spent):
    v = pace_advisor.resolve_pace(None, _window(weekly_allowance=100.0, spent_this_week=spent))
    assert v.pct_over == 0, f"spent={spent} should not read as over"


def test_cycle_and_no_cycle_users_get_identical_verdicts():
    """Equivalent spent/allowance/days → the same tier and the same percentages,
    whichever budgeting mode the user is in."""
    for allowance, spent, elapsed, remaining in [
        (76.78, 36.58, 3, 4),
        (100.0, 133.0, 4, 3),
        (250.0, 0.0, 0, 7),
        (250.0, 20.0, 5, 2),
    ]:
        cycle_v = pace_advisor.resolve_pace(
            _cycle(weekly_allowance=allowance, spent_this_week=spent,
                   days_elapsed_in_week=elapsed, days_remaining_in_week=remaining),
            None,
        )
        window_v = pace_advisor.resolve_pace(
            None,
            _window(weekly_allowance=allowance, spent_this_week=spent,
                    days_elapsed_in_week=elapsed, days_remaining_in_week=remaining),
        )
        assert cycle_v == window_v, f"parity broken for {allowance=} {spent=} {elapsed=}"


def test_no_goal_window_yields_no_verdict():
    # Monthly goal not set → has_goal False, allowance 0. Never a baseless %.
    v = pace_advisor.resolve_pace(None, _window(has_goal=False, weekly_allowance=0.0))
    assert not v.has_verdict
    assert v.pct_used == 0 and v.pct_over == 0


def test_zero_allowance_window_yields_no_verdict():
    # Goal set but fully spent → allowance 0. Guard against divide-by-zero.
    v = pace_advisor.resolve_pace(None, _window(weekly_allowance=0.0, spent_this_week=50.0))
    assert not v.has_verdict


def test_active_cycle_wins_over_budget_window():
    # A user can only be in one mode; if both blocks arrive, the active cycle is
    # authoritative (it is what the budget bar renders).
    cycle = _cycle(weekly_allowance=100.0, spent_this_week=10.0, days_elapsed_in_week=5, days_remaining_in_week=2)
    window = _window(weekly_allowance=100.0, spent_this_week=133.0)
    assert pace_advisor.resolve_pace(cycle, window).tier == pace_advisor.TIER_GREAT


def test_no_cycle_nudge_never_shows_over_percentage_while_under_budget():
    window = _window(weekly_allowance=76.78, spent_this_week=36.58)
    txs = [_var_tx(36.58, date(2026, 5, 4))]
    nudge = nudge_generator.generate_nudge(
        tier="pacing_warn", risk_flags=[], profile=_profile(language="RU"),
        transactions=txs, analysis_date=date(2026, 5, 4), predicted_balance=100.0,
        budget_window=window,
    )
    assert "%" not in nudge or "перерасход" not in nudge.lower()


def test_no_cycle_nudge_over_budget_shows_true_overage():
    window = _window(weekly_allowance=100.0, spent_this_week=133.0, days_elapsed_in_week=4)
    txs = [_var_tx(133.0, date(2026, 5, 5))]
    nudge = nudge_generator.generate_nudge(
        tier="pacing_over", risk_flags=[], profile=_profile(language="EN"),
        transactions=txs, analysis_date=date(2026, 5, 5), predicted_balance=-50.0,
        budget_window=window,
    )
    assert "33%" in nudge
