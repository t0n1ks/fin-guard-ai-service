from typing import Optional

from pydantic import BaseModel


class AnalyzeBehaviorResponse(BaseModel):
    financial_health_score: int
    sustainability_score: int
    predicted_end_of_month_balance: float
    predicted_savings_balance: float = 0.0
    tamagotchi_mood: str
    smart_nudge: str
    spending_tier: str
    risk_flags: list[str]
    # Locally-learned, per-user calibrated daily variable spend (EWMA) and how
    # many observations have folded into it. Additive/optional — defaults keep
    # older clients unaffected.
    calibrated_daily_spend: float = 0.0
    learner_observations: int = 0


class NextActionResponse(BaseModel):
    type: str
    content: Optional[str] = None
    animation_hint: str
    # All 4 language versions keyed by ISO code (en/de/ru/uk).
    # Present for FACT and JOKE types so the frontend can re-render on language switch.
    all_translations: Optional[dict[str, str]] = None
