import hmac

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.models.request import AnalyzeBehaviorRequest
from app.models.response import AnalyzeBehaviorResponse
from app.services import (
    forecaster,
    health_scorer,
    mood_engine,
    nudge_generator,
    sustainability_scorer,
    tier_calculator,
)
from app.services.content_tracker import store_pending_advice
from app.services.visit_tracker import record_visit

router = APIRouter()


def verify_api_key(x_brain_api_key: str = Header(default="")) -> None:
    if settings.maintenance_mode:
        return
    if not hmac.compare_digest(x_brain_api_key, settings.effective_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post(
    "/analyze-behavior",
    response_model=AnalyzeBehaviorResponse,
    dependencies=[Depends(verify_api_key)],
)
def analyze_behavior(body: AnalyzeBehaviorRequest) -> AnalyzeBehaviorResponse:
    profile = body.user_profile
    transactions = body.transactions
    today = body.analysis_date

    health_score, risk_flags = health_scorer.compute_financial_health_score(
        transactions, profile, today
    )
    sustainability = sustainability_scorer.compute_sustainability_score(transactions, today)
    predicted_balance = forecaster.predict_end_of_month_balance(
        transactions, today, profile.expected_salary
    )
    mood = mood_engine.get_tamagotchi_mood(health_score)
    tier = tier_calculator.compute_spending_tier(transactions, profile, today)
    nudge = nudge_generator.generate_nudge(
        tier, risk_flags, profile, transactions, today, predicted_balance,
        user_categories=body.user_categories,
    )

    store_pending_advice(user_id=profile.user_id, advice=nudge)
    record_visit(user_id=profile.user_id)

    return AnalyzeBehaviorResponse(
        financial_health_score=health_score,
        sustainability_score=sustainability,
        predicted_end_of_month_balance=predicted_balance,
        tamagotchi_mood=mood,
        smart_nudge=nudge,
        spending_tier=tier,
        risk_flags=risk_flags,
    )
