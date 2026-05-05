from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.models.request import TransactionItem, UserProfile

_TEMPLATES: dict[str, list[str]] = {
    "pacing_over": [
        "You're {pct_over}% over your weekly budget. Consider skipping {top_cat} this week.",
        "Weekly overspend by {pct_over}%. Your {top_cat} spending is the main driver.",
    ],
    "pacing_warn": [
        "You've used {pct_used}% of your weekly allowance with {days_left} days to go.",
        "Slow down — {pct_used}% of weekly budget spent, {days_left} days remain.",
    ],
    "pacing_great": [
        "Excellent pacing! Only {pct_used}% of weekly budget used on {day_name}.",
        "Well under budget this week ({pct_used}% used). Keep it up!",
    ],
    "salary_just_in": [
        "Salary received! You now have {effective_income} {currency}. Monthly goal: {goal} {currency}.",
        "Fresh funds arrived. Remember your {goal} {currency} monthly spending goal.",
    ],
    "balanced": [
        "Great balance across categories this week! No single area dominates your spending.",
        "Your spending is well-distributed. Keep the diversity going!",
    ],
    "pacing_good": [
        "You're on track! Trimming {top_cat} by 15% could save ~{potential_saving} {currency} this month.",
        "Good pacing. {days_left} days left with {budget_remaining} {currency} in weekly allowance.",
    ],
    "predicted_shortfall": [
        "Projected end-of-month balance: {predicted_balance} {currency}. A shortfall is likely — review expenses.",
        "Your spending trend points to a {predicted_balance} {currency} finish. Consider cutting back now.",
    ],
    "no_income_logged": [
        "No income logged this month. Add your salary to Settings to unlock budget tracking.",
        "Set your expected salary in Settings so I can give you accurate budget advice.",
    ],
    "on_track": [
        "You're on track for a {predicted_balance} {currency} balance at month end.",
        "Looking good — projected month-end balance is {predicted_balance} {currency}.",
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
    top_cat = max(cat_map, key=lambda k: cat_map[k]) if cat_map else "miscellaneous"

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
        return template.format(**ctx)
    except KeyError:
        return random.choice(_TEMPLATES["on_track"]).format(**ctx)
