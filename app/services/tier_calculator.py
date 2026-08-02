from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.models.request import SalaryCycleInfo, TransactionItem, UserProfile
from app.services import pace_advisor


def _get_monday(d: date) -> date:
    return d - timedelta(days=d.isoweekday() - 1)


def _cycle_pace_usable(salary_cycle: SalaryCycleInfo | None) -> bool:
    """A pace verdict is only valid on top of a real, active weekly budget."""
    return bool(
        salary_cycle is not None
        and salary_cycle.cycle_active
        and salary_cycle.weekly_allowance > 0
    )


def compute_spending_tier(
    transactions: list[TransactionItem],
    profile: UserProfile,
    analysis_date: date,
    salary_cycle: SalaryCycleInfo | None = None,
) -> str:
    monday = _get_monday(analysis_date)

    week_expenses = [
        tx for tx in transactions
        if tx.type == "expense" and tx.date >= monday
    ]
    week_spending = sum(tx.amount for tx in week_expenses)

    three_days_ago = analysis_date - timedelta(days=3)
    salary_just_in = any(
        tx for tx in transactions
        if tx.type == "income"
        and tx.income_type in ("one_time", "")
        and tx.date >= three_days_ago
    )

    cat_map: dict[str, float] = defaultdict(float)
    for tx in week_expenses:
        cat_map[tx.category.name] += tx.amount

    cat_count = len(cat_map)
    max_share = (
        max(cat_map.values()) / week_spending
        if week_spending > 0 and cat_count > 0
        else 0.0
    )
    is_balanced = cat_count >= 2 and max_share < 0.45

    if salary_just_in:
        return "salary_just_in"

    # ── Cycle users: authoritative, pace-aware verdict ────────────────────────
    # Preferred path — uses the exact weekly numbers the budget bar shows, so the
    # percentage/tone can never contradict it. Legacy path below only runs when
    # there is no active cycle (or an older Go build sent no weekly window).
    if _cycle_pace_usable(salary_cycle):
        verdict = pace_advisor.evaluate_pace(
            weekly_allowance=salary_cycle.weekly_allowance,
            spent_this_week=salary_cycle.spent_this_week,
            days_elapsed_in_week=salary_cycle.days_elapsed_in_week,
            days_remaining_in_week=salary_cycle.days_remaining_in_week,
        )
        if verdict.has_verdict:
            # Surface category balance only when the pace itself is calm.
            if verdict.tier == pace_advisor.TIER_GOOD and is_balanced and week_spending > 0:
                return "balanced"
            return verdict.tier

    # ── Legacy fallback (no active cycle) ─────────────────────────────────────
    weekly_limit = profile.monthly_spending_goal / 4.3 if profile.monthly_spending_goal > 0 else 0.0
    pace = week_spending / weekly_limit if weekly_limit > 0 else 0.0

    # isoweekday: 1=Mon … 7=Sun; Wednesday = 3
    is_past_wednesday = analysis_date.isoweekday() >= 3

    if weekly_limit > 0 and pace > 1.2:
        return "pacing_over"
    if weekly_limit > 0 and pace > 0.8:
        return "pacing_warn"
    if weekly_limit > 0 and pace < 0.5 and is_past_wednesday and week_spending > 0:
        return "pacing_great"
    if is_balanced and week_spending > 0 and pace < 0.8:
        return "balanced"
    return "pacing_good"
