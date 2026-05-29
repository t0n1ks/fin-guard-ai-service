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
    fixed_exp_category_id: int = 0  # DB category ID for Fixed Payments transactions
    cycle_start_at: Optional[str] = None  # ISO timestamp string
    next_payday_at: Optional[str] = None  # ISO timestamp string; cycle end


class AnalyzeBehaviorRequest(BaseModel):
    user_profile: UserProfile
    transactions: list[TransactionItem]
    analysis_date: date
    user_categories: list[str] = Field(default_factory=list)
    salary_cycle: Optional[SalaryCycleInfo] = None
