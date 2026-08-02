from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.models.request import (
    BudgetWindowInfo,
    SalaryCycleInfo,
    TransactionItem,
    UserProfile,
)
from app.services import pace_advisor


def _get_monday(d: date) -> date:
    return d - timedelta(days=d.isoweekday() - 1)


def compute_spending_tier(
    transactions: list[TransactionItem],
    profile: UserProfile,
    analysis_date: date,
    salary_cycle: SalaryCycleInfo | None = None,
    budget_window: BudgetWindowInfo | None = None,
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

    # ── Authoritative, pace-aware verdict — BOTH user types ───────────────────
    # Cycle users are served by salary_cycle, no-cycle monthly-goal users by
    # budget_window. Either way the numbers are the exact ones the budget bar
    # shows, so the percentage/tone can never contradict it.
    verdict = pace_advisor.resolve_pace(salary_cycle, budget_window)
    if verdict.has_verdict:
        # Surface category balance only when the pace itself is calm.
        if verdict.tier == pace_advisor.TIER_GOOD and is_balanced and week_spending > 0:
            return "balanced"
        return verdict.tier

    # ── No authoritative weekly window (no cycle, no monthly goal) ────────────
    # Never invent a pace percentage from monthly_spending_goal / 4.3 — degrade to
    # percentage-free copy instead.
    if is_balanced and week_spending > 0:
        return "balanced"
    return "pacing_good"
