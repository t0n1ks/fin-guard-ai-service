from typing import Optional

from pydantic import BaseModel


class AnalyzeBehaviorResponse(BaseModel):
    financial_health_score: int
    sustainability_score: int
    predicted_end_of_month_balance: float
    tamagotchi_mood: str
    smart_nudge: str
    spending_tier: str
    risk_flags: list[str]


class NextActionResponse(BaseModel):
    type: str
    content: Optional[str] = None
    animation_hint: str
