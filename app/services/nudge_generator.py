from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.models.request import TransactionItem, UserProfile

_TEMPLATES: dict[str, list[str]] = {
    "pacing_over": [
        "⚠️ {pct_over}% over budget! Cut {top_cat} now.",
        "{top_cat} blew your week by {pct_over}%. 🕳️",
    ],
    "pacing_warn": [
        "{pct_used}% used, {days_left}d left. Slow it down! 🐢",
        "Heads up: {pct_used}% of week spent, {days_left} days to go.",
    ],
    "pacing_great": [
        "Houston, only {pct_used}% used on {day_name}. 🚀",
        "Stellar pace — {pct_used}% burned. All clear! ✨",
    ],
    "salary_just_in": [
        "💰 Payday! Keep goal: {goal} {currency}. Spend wisely.",
        "Fresh cash in! Stick to your {goal} {currency} plan.",
    ],
    "balanced": [
        "Spending orbit stable — no leaks detected! 🛸",
        "All systems balanced. Solid week! 💪",
    ],
    "pacing_good": [
        "On track! Trim {top_cat} 15% → ~{potential_saving} {currency} saved.",
        "{days_left}d left, {budget_remaining} {currency} to spare. 👌",
    ],
    "predicted_shortfall": [
        "Shortfall ahead: {predicted_balance} {currency}. Cut now! 🔴",
        "Trending to {predicted_balance} {currency} month-end. Danger! ⚠️",
    ],
    "no_income_logged": [
        "No income logged. Add salary in Settings! 📊",
        "Set expected salary in Settings to unlock insights.",
    ],
    "on_track": [
        "Trajectory: {predicted_balance} {currency} at month's end. 🌙",
        "Orbit stable — {predicted_balance} {currency} projected. ✅",
    ],
}


def _build_context(
    transactions: list[TransactionItem],
    profile: UserProfile,
    analysis_date: date,
    predicted_balance: float,
) -> dict[str, Any]:
    monday = analysis_date - timedelta(days=analysis_date.isoweekday() - 1)
    week_expenses = [tx for tx in transactions if tx.type == "expense" and tx.date >= monday]
    week_spending = sum(tx.amount for tx in week_expenses)

    month_income = sum(
        tx.amount for tx in transactions
        if tx.type == "income"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    )
    effective_income = month_income if month_income > 0 else profile.expected_salary

    weekly_limit = profile.monthly_spending_goal / 4.3 if profile.monthly_spending_goal > 0 else 0.0
    pace = week_spending / weekly_limit if weekly_limit > 0 else 0.0

    cat_map: dict[str, float] = defaultdict(float)
    for tx in week_expenses:
        cat_map[tx.category.name] += tx.amount
    raw_top = max(cat_map, key=lambda k: cat_map[k]) if cat_map else "misc"
    top_cat = raw_top[:16] if len(raw_top) > 16 else raw_top

    days_left = 7 - analysis_date.isoweekday()
    pct_used = int(round(pace * 100))
    pct_over = max(0, pct_used - 100)
    budget_remaining = round(max(0.0, weekly_limit - week_spending), 2)
    potential_saving = round(
        sum(tx.amount for tx in week_expenses if tx.category.name == top_cat) * 0.15, 2
    )

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = day_names[analysis_date.isoweekday() - 1]

    return {
        "pct_over": pct_over,
        "pct_used": pct_used,
        "days_left": days_left,
        "top_cat": top_cat,
        "effective_income": round(effective_income, 2),
        "goal": round(profile.monthly_spending_goal, 2),
        "currency": profile.currency,
        "potential_saving": potential_saving,
        "budget_remaining": budget_remaining,
        "predicted_balance": predicted_balance,
        "day_name": day_name,
    }


def generate_nudge(
    tier: str,
    risk_flags: list[str],
    profile: UserProfile,
    transactions: list[TransactionItem],
    analysis_date: date,
    predicted_balance: float,
) -> str:
    ctx = _build_context(transactions, profile, analysis_date, predicted_balance)

    if "no_income" in risk_flags and profile.expected_salary == 0:
        key = "no_income_logged"
    elif "expenses_exceed_income" in risk_flags and predicted_balance < 0:
        key = "predicted_shortfall"
    elif tier in _TEMPLATES:
        key = tier
    else:
        key = "on_track"

    template = random.choice(_TEMPLATES[key])
    try:
        result = template.format(**ctx)
    except KeyError:
        result = random.choice(_TEMPLATES["on_track"]).format(**ctx)
    return result if len(result) <= 99 else result[:99] + "…"
