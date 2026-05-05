from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date

from sklearn.linear_model import LinearRegression

from app.models.request import TransactionItem, UserProfile


def predict_end_of_month_balance(
    transactions: list[TransactionItem],
    analysis_date: date,
    expected_salary: float,
) -> float:
    month_start = analysis_date.replace(day=1)

    month_expenses = [
        tx for tx in transactions
        if tx.type == "expense"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    ]
    month_income = [
        tx for tx in transactions
        if tx.type == "income"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    ]

    total_income = sum(tx.amount for tx in month_income)
    effective_income = total_income if total_income > 0 else expected_salary

    day_buckets: dict[int, float] = defaultdict(float)
    for tx in month_expenses:
        day_num = (tx.date - month_start).days + 1
        day_buckets[day_num] += tx.amount

    days_elapsed = (analysis_date - month_start).days + 1
    X: list[list[int]] = []
    y: list[float] = []
    running = 0.0
    for d in range(1, days_elapsed + 1):
        running += day_buckets.get(d, 0.0)
        X.append([d])
        y.append(running)

    total_expense_so_far = running
    days_in_month = calendar.monthrange(analysis_date.year, analysis_date.month)[1]
    remaining_days = days_in_month - days_elapsed

    if len(X) < 7:
        daily_avg = total_expense_so_far / max(days_elapsed, 1)
        predicted_total_expense = total_expense_so_far + daily_avg * remaining_days
    else:
        model = LinearRegression()
        model.fit(X, y)
        predicted_total_expense = float(model.predict([[days_in_month]])[0])
        predicted_total_expense = max(predicted_total_expense, total_expense_so_far)

    predicted_balance = effective_income - predicted_total_expense
    return round(predicted_balance, 2)
