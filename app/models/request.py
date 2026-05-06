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
        return s if s in {"EN", "RU", "UA", "DE"} else "EN"

    @field_validator("manual_next_payday", mode="before")
    @classmethod
    def coerce_empty_string(cls, v: object) -> Optional[str]:
        if v == "" or v == "null":
            return None
        return v  # type: ignore[return-value]


class AnalyzeBehaviorRequest(BaseModel):
    user_profile: UserProfile
    transactions: list[TransactionItem]
    analysis_date: date
