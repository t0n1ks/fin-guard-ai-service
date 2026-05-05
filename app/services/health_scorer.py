from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from app.models.request import TransactionItem, UserProfile


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")[:20]


def _same_month(d: date, ref: date) -> bool:
    return d.year == ref.year and d.month == ref.month


def compute_financial_health_score(
    transactions: list[TransactionItem],
    profile: UserProfile,
    analysis_date: date,
) -> tuple[int, list[str]]:
    month_expenses = [tx for tx in transactions if tx.type == "expense" and _same_month(tx.date, analysis_date)]
    month_income = [tx for tx in transactions if tx.type == "income" and _same_month(tx.date, analysis_date)]

    total_expense = sum(tx.amount for tx in month_expenses)
    total_income = sum(tx.amount for tx in month_income)
    if total_income == 0:
        total_income = profile.expected_salary

    ratio = total_expense / max(total_income, 1)
    ratio_score = _clamp(100 - ratio * 100, 0, 100)

    if profile.monthly_spending_goal > 0:
        goal_pct = total_expense / profile.monthly_spending_goal
        goal_score = _clamp(100 - (goal_pct - 1.0) * 200, 0, 100)
    else:
        goal_score = 100.0 if total_expense == 0 else 50.0

    category_totals: dict[str, float] = defaultdict(float)
    for tx in month_expenses:
        category_totals[tx.category.name] += tx.amount

    dominant_share = 0.0
    top_cat = ""
    if total_expense > 0 and category_totals:
        top_cat = max(category_totals, key=lambda k: category_totals[k])
        dominant_share = category_totals[top_cat] / total_expense

    excess = max(dominant_share - 0.5, 0)
    diversity_score = _clamp(100 * (1 - excess * 2), 0, 100)

    savings_rate = (total_income - total_expense) / max(total_income, 1)
    savings_score = _clamp(savings_rate * 100, 0, 100)

    raw = (
        ratio_score * 0.40
        + goal_score * 0.30
        + diversity_score * 0.20
        + savings_score * 0.10
    )
    final_score = int(_clamp(round(raw), 1, 100))

    risk_flags: list[str] = []
    if dominant_share > 0.5 and top_cat:
        risk_flags.append(f"high_{_slugify(top_cat)}_spend")
    if sum(tx.amount for tx in month_income) == 0 and profile.expected_salary == 0:
        risk_flags.append("no_income")
    if ratio > 1.0:
        risk_flags.append("expenses_exceed_income")

    return final_score, risk_flags
