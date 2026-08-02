from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CategoryInfo(BaseModel):
    id: int
    name: str


class TransactionItem(BaseModel):
    id: int
    amount: float = Field(gt=0)
    category: CategoryInfo
    date: date
    type: str
    income_type: str = "one_time"
    description: Optional[str] = None


class UserProfile(BaseModel):
    user_id: int
    currency: str = "USD"
    monthly_spending_goal: float = 0.0
    expected_salary: float = 0.0
    payday_mode: str = "smart"
    fixed_payday: int = 0
    manual_next_payday: Optional[str] = None
    ai_humor_enabled: bool = False
    language: str = "EN"

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v: object) -> str:
        s = str(v).upper().strip() if v else "EN"
        if s == "UK":  # ISO 639-1 for Ukrainian → internal code
            s = "UA"
        return s if s in {"EN", "RU", "UA", "DE"} else "EN"

    @field_validator("manual_next_payday", mode="before")
    @classmethod
    def coerce_empty_string(cls, v: object) -> Optional[str]:
        if v == "" or v == "null":
            return None
        return v  # type: ignore[return-value]


class SalaryCycleInfo(BaseModel):
    """Optional — present only when the user has set up a salary cycle."""
    total_income: float = 0.0
    needs_pct: float = 50.0
    wants_pct: float = 30.0
    savings_pct: float = 20.0
    savings_limit: float = 0.0
    fixed_needs_total: float = 0.0
    fixed_wants_total: float = 0.0
    var_needs_budget: float = 0.0
    var_wants_budget: float = 0.0
    fixed_exp_category_id: int = 0    # DB category ID for Fixed Payments transactions
    saved_money_category_id: int = 0  # DB category ID for the savings pool
    saved_money_balance: float = 0.0  # authoritative pool balance from the backend
    cycle_start_at: Optional[str] = None  # ISO timestamp string
    next_payday_at: Optional[str] = None  # ISO timestamp string; cycle end

    # ── Authoritative weekly-pace window (Go computeCycleStats) ───────────────
    # These are the EXACT numbers the Dashboard budget bar renders. The pace
    # advisor consumes them verbatim and never re-derives weekly math, so the
    # UFO's verdict can never contradict the bar. Defaults keep older Go builds
    # (which don't send these) validating and falling back to the legacy path.
    weekly_allowance: float = 0.0        # "Можно потратить" for the current week
    spent_this_week: float = 0.0         # variable spend inside the 7-day window
    days_elapsed_in_week: int = 0        # 0..7 days into the current cycle-week
    days_remaining_in_week: int = 0      # days left in the current cycle-week
    days_until_next_payout: int = 0      # days left in the whole cycle
    cycle_active: bool = False           # cycle exists and today is within it
    is_lite: bool = False                # user opted into Lite mode


class BudgetWindowInfo(BaseModel):
    """Optional — present for users WITHOUT an active salary cycle.

    The authoritative monthly budget window computed by Go (computeBudgetWindow):
    the exact numbers the Dashboard budget bar renders. The weekly fields are named
    identically to SalaryCycleInfo's so pace_advisor.resolve_pace can consume either
    source through one code path. Defaults keep older Go builds (which don't send
    this block) validating — they simply get no pace verdict instead of a verdict
    invented from monthly_spending_goal / 4.3.
    """
    has_goal: bool = False
    monthly_budget: float = 0.0
    spent_this_window: float = 0.0

    weekly_allowance: float = 0.0          # "Можно потратить" for the current week
    spent_this_week: float = 0.0           # expenses inside the current week window
    days_elapsed_in_week: int = 0          # 0..7 COMPLETED days into the week
    days_remaining_in_week: int = 0        # days left in the week, capped by the month
    days_remaining_in_window: int = 0      # days left in the calendar month


class AnalyzeBehaviorRequest(BaseModel):
    user_profile: UserProfile
    transactions: list[TransactionItem]
    analysis_date: date
    user_categories: list[str] = Field(default_factory=list)
    salary_cycle: Optional[SalaryCycleInfo] = None
    budget_window: Optional[BudgetWindowInfo] = None
