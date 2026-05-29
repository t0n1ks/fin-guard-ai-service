"""
Enterprise-grade prediction engine for the FinGuard salary cycle tracker.

Core design principles:
  - Fixed expenses (tagged by DB category ID) are EXCLUDED from daily run-rate —
    they are committed costs already reflected in the cycle budget ceiling.
  - Daily variable spending is estimated via an exponentially-weighted moving
    average (EWMA) over the last 14 days, giving more weight to recent behaviour.
  - A simple weekday/weekend seasonality multiplier corrects for the well-known
    pattern that weekend discretionary spending is ~30 % higher than weekday.
  - When salary-cycle data is available, all projections are anchored to the
    cycle's variable allowance rather than a naive calendar-month boundary.
  - Legacy path (no cycle data) falls back to linear regression on month data.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from app.models.request import SalaryCycleInfo, TransactionItem, UserProfile

# ── Constants ────────────────────────────────────────────────────────────────

_EWMA_LOOKBACK = 14          # days of history for moving average
_EWMA_DECAY = 0.85           # weight decay per day (0.85^1 = most-recent, 0.85^14 ≈ 0.10)
_WEEKEND_FACTOR = 1.30       # Sat/Sun spend ~30 % above weekday average
_WEEKDAY_FACTOR = 1.00


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_fixed(tx: TransactionItem, fixed_cat_id: int) -> bool:
    """True if this transaction is a committed fixed expense to exclude from run-rate."""
    return fixed_cat_id > 0 and tx.category.id == fixed_cat_id


def _daily_variable_rate(
    transactions: list[TransactionItem],
    today: date,
    cycle_start: date,
    fixed_cat_id: int,
) -> float:
    """
    Exponentially-weighted moving average of daily variable expenditure
    over the last _EWMA_LOOKBACK days (or since cycle start, whichever is shorter).
    Returns 0.0 if there is no data.
    """
    lookback_start = max(today - timedelta(days=_EWMA_LOOKBACK - 1), cycle_start)

    # Aggregate variable expenses by day
    daily: dict[date, float] = defaultdict(float)
    for tx in transactions:
        if tx.type != "expense":
            continue
        if _is_fixed(tx, fixed_cat_id):
            continue
        if lookback_start <= tx.date <= today:
            daily[tx.date] += tx.amount

    if not daily:
        return 0.0

    # EWMA: most-recent day gets weight 1.0, each day further back is multiplied
    # by _EWMA_DECAY. Final result is the weighted average daily spend.
    total_weight = 0.0
    weighted_sum = 0.0
    for day, amount in daily.items():
        age = (today - day).days  # 0 = today, 1 = yesterday, …
        w = _EWMA_DECAY ** age
        weighted_sum += amount * w
        total_weight += w

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _project_spend(avg_daily: float, from_date: date, days: int) -> float:
    """
    Project total spending over `days` future days starting from `from_date`,
    applying weekend / weekday seasonality.
    """
    total = 0.0
    for offset in range(days):
        proj_date = from_date + timedelta(days=offset + 1)
        factor = _WEEKEND_FACTOR if proj_date.isoweekday() >= 6 else _WEEKDAY_FACTOR
        total += avg_daily * factor
    return total


# ── Public API ────────────────────────────────────────────────────────────────

def predict_end_of_month_balance(
    transactions: list[TransactionItem],
    analysis_date: date,
    expected_salary: float,
    salary_cycle: Optional[SalaryCycleInfo] = None,
) -> float:
    """
    Primary balance prediction entry point.
    Delegates to cycle-aware or legacy algorithm based on available data.
    """
    if salary_cycle and salary_cycle.cycle_start_at:
        return _cycle_prediction(transactions, analysis_date, salary_cycle)
    return _legacy_prediction(transactions, analysis_date, expected_salary)


def predict_savings_accumulation(
    transactions: list[TransactionItem],
    analysis_date: date,
    profile: UserProfile,
    salary_cycle: Optional[SalaryCycleInfo] = None,
) -> float:
    """
    Estimate total accumulated savings balance (historical + projected current cycle).
    """
    current_key = (analysis_date.year, analysis_date.month)
    fixed_cat_id = salary_cycle.fixed_exp_category_id if salary_cycle else 0

    # Net per calendar month — exclude fixed expenses from all sums so the savings
    # projection reflects only the discretionary portion of the cycle budget.
    monthly_net: dict[tuple[int, int], float] = defaultdict(float)
    for tx in transactions:
        if _is_fixed(tx, fixed_cat_id):
            continue
        key = (tx.date.year, tx.date.month)
        delta = tx.amount if tx.type == "income" else -tx.amount
        monthly_net[key] += delta

    historical = sum(v for k, v in monthly_net.items() if k < current_key)
    current_projected = predict_end_of_month_balance(
        transactions, analysis_date, profile.expected_salary, salary_cycle
    )
    return round(historical + current_projected, 2)


# ── Internal algorithms ───────────────────────────────────────────────────────

# Below this many days of cycle history, EWMA is too volatile — a single day-1
# grocery run would be projected across the whole cycle. Use a simple capped
# average instead until enough data accumulates.
_SPARSE_DATA_DAYS = 5


def _cycle_prediction(
    transactions: list[TransactionItem],
    today: date,
    cycle: SalaryCycleInfo,
) -> float:
    """
    Cycle-aware, stabilized prediction of end-of-cycle balance vs the variable
    (discretionary) allowance. Fixed expenses are excluded from the run-rate.

    Stabilization guards (prevent the "unhinged deficit" regression):
      * Sparse-data fallback: with < _SPARSE_DATA_DAYS of history, use a simple
        average instead of EWMA (EWMA over 1–4 days is dangerously volatile).
      * Sanity cap: the projected daily rate can never exceed
        (remaining_allowance / days_remaining) * 1.2 — so the projection stays
        anchored to what's actually left, producing human-readable numbers.

    Returns remaining_allowance − projected_remaining_variable_spend.
    Negative = projected deficit; positive = projected surplus.
    """
    fixed_cat_id = cycle.fixed_exp_category_id

    # Parse cycle boundaries (ISO timestamps → date).
    try:
        cycle_start = date.fromisoformat(cycle.cycle_start_at[:10])
    except (ValueError, TypeError):
        cycle_start = today.replace(day=1)

    # Real cycle length from next_payday when available; else 30-day default.
    cycle_total_days = 30
    if cycle.next_payday_at:
        try:
            next_payday = date.fromisoformat(cycle.next_payday_at[:10])
            span = (next_payday - cycle_start).days
            if span >= 7:
                cycle_total_days = span
        except (ValueError, TypeError):
            pass

    # Variable allowance = net discretionary budget for this cycle.
    discretionary = (cycle.var_needs_budget + cycle.var_wants_budget) or cycle.total_income * 0.8

    spent_variable = sum(
        tx.amount
        for tx in transactions
        if tx.type == "expense"
        and not _is_fixed(tx, fixed_cat_id)
        and tx.date >= cycle_start
    )
    remaining_allowance = max(0.0, discretionary - spent_variable)

    cycle_days_elapsed = max(1, (today - cycle_start).days)
    days_remaining = max(0, cycle_total_days - cycle_days_elapsed)
    if days_remaining == 0:
        return round(remaining_allowance, 2)

    # Choose a daily run-rate estimator.
    if cycle_days_elapsed < _SPARSE_DATA_DAYS:
        # Sparse: simple average of variable spend so far. Conservative and
        # immune to EWMA's single-outlier amplification.
        avg_daily = spent_variable / cycle_days_elapsed
    else:
        avg_daily = _daily_variable_rate(transactions, today, cycle_start, fixed_cat_id)

    if avg_daily <= 0.0:
        # No spending yet — assume the user paces evenly across the cycle.
        avg_daily = discretionary / cycle_total_days

    # Sanity cap (daily): never project a daily run-rate above 1.2× the
    # even-pacing rate of whatever allowance remains.
    cap = (remaining_allowance / days_remaining) * 1.2
    if cap > 0:
        avg_daily = min(avg_daily, cap)

    projected_remaining = _project_spend(avg_daily, today, days_remaining)

    # Sanity cap (total): seasonality must not push the projection past the
    # remaining allowance + 20% buffer. This guarantees the projected deficit can
    # never exceed 20% of the remaining allowance — no "unhinged" extremes.
    projected_remaining = min(projected_remaining, remaining_allowance * 1.2)

    predicted_balance = remaining_allowance - projected_remaining
    return round(predicted_balance, 2)


def _legacy_prediction(
    transactions: list[TransactionItem],
    analysis_date: date,
    expected_salary: float,
) -> float:
    """
    Legacy linear-regression prediction for users without a salary cycle.
    Projects month-end balance based on current-month spending trend.
    """
    month_start = analysis_date.replace(day=1)

    month_expenses = [
        tx for tx in transactions
        if tx.type == "expense"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    ]
    total_income = sum(
        tx.amount for tx in transactions
        if tx.type == "income"
        and tx.date.year == analysis_date.year
        and tx.date.month == analysis_date.month
    )
    effective_income = total_income if total_income > 0 else expected_salary

    day_totals: dict[int, float] = defaultdict(float)
    for tx in month_expenses:
        day_num = (tx.date - month_start).days + 1
        day_totals[day_num] += tx.amount

    days_elapsed = (analysis_date - month_start).days + 1
    total_expense_so_far = sum(day_totals[d] for d in range(1, days_elapsed + 1))
    days_in_month = calendar.monthrange(analysis_date.year, analysis_date.month)[1]
    remaining_days = days_in_month - days_elapsed

    # EWMA over available history for the legacy path as well
    if days_elapsed >= 3:
        weights_sum = 0.0
        weighted_exp = 0.0
        for d in range(1, days_elapsed + 1):
            age = days_elapsed - d  # 0 = today, older = higher age
            w = _EWMA_DECAY ** age
            weighted_exp += day_totals.get(d, 0.0) * w
            weights_sum += w
        avg_daily = weighted_exp / weights_sum if weights_sum > 0 else 0.0
    else:
        avg_daily = total_expense_so_far / max(days_elapsed, 1)

    projected_additional = _project_spend(avg_daily, analysis_date, remaining_days)
    predicted_total_expense = total_expense_so_far + projected_additional
    return round(effective_income - predicted_total_expense, 2)
