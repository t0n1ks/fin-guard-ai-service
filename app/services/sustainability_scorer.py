from __future__ import annotations

from datetime import date

from app.models.request import TransactionItem

_GREEN = {
    "transit", "bike", "cycling", "organic", "health", "fitness",
    "education", "repair", "garden", "gardening", "grocery", "groceries",
    "pharmacy", "medical", "vegetarian", "vegan", "sport", "sports",
    "library", "book",
}

_NEGATIVE = {
    "fast food", "alcohol", "tobacco", "smoking", "gambling", "luxury",
    "fuel", "petrol", "gas", "betting", "casino", "nightclub", "junk",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_sustainability_score(
    transactions: list[TransactionItem],
    analysis_date: date,
) -> int:
    month_expenses = [
        tx for tx in transactions
        if tx.type == "expense"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    ]
    total_expense = sum(tx.amount for tx in month_expenses)

    green_spend = 0.0
    negative_spend = 0.0

    for tx in month_expenses:
        cat = tx.category.name.lower()
        if any(kw in cat for kw in _GREEN):
            green_spend += tx.amount
        elif any(kw in cat for kw in _NEGATIVE):
            negative_spend += tx.amount

    raw = 50.0 + ((green_spend - negative_spend * 1.5) / max(total_expense, 1)) * 50.0
    return int(_clamp(round(raw), 1, 100))
