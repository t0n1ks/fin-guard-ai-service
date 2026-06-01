"""
Lightweight per-user learning endpoint.

The Go backend streams a small, coalesced observation here after transaction
mutations. Each call performs a single O(1) exponential-smoothing update of the
user's state — there is intentionally no model fit / retraining loop, so the
free-tier instance stays cheap no matter how often observations arrive.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.endpoints.analyze import verify_api_key
from app.services import learner

router = APIRouter()


class LearnRequest(BaseModel):
    user_id: int
    observed_daily_spend: float = Field(default=0.0, ge=0)
    observed_daily_savings: float = Field(default=0.0, ge=0)
    days_remaining: int = Field(default=0, ge=0)
    current_savings_balance: float = 0.0


class LearnResponse(BaseModel):
    user_id: int
    ewma_daily_spend: float
    ewma_daily_savings: float
    observations: int
    projected_spend: float
    projected_savings_balance: float


@router.post("/learn", response_model=LearnResponse, dependencies=[Depends(verify_api_key)])
def learn(body: LearnRequest) -> LearnResponse:
    state = learner.record_observation(
        body.user_id, body.observed_daily_spend, body.observed_daily_savings
    )
    pred = learner.predict(state, body.days_remaining, body.current_savings_balance)
    return LearnResponse(
        user_id=body.user_id,
        ewma_daily_spend=state["ewma_daily_spend"],
        ewma_daily_savings=state["ewma_daily_savings"],
        observations=state["observations"],
        projected_spend=pred["projected_spend"],
        projected_savings_balance=pred["projected_savings_balance"],
    )
