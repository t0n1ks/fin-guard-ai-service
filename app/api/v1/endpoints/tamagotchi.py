import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query

from app.api.v1.endpoints.analyze import verify_api_key
from app.models.response import NextActionResponse
from app.services.tamagotchi_action import get_next_action

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_LANGUAGES = {"EN", "RU", "UA", "DE"}


class ContentFeedback(BaseModel):
    user_id: int
    accepted: bool


@router.get(
    "/tamagotchi/next-action",
    response_model=NextActionResponse,
    dependencies=[Depends(verify_api_key)],
)
def next_tamagotchi_action(
    user_id: int = Query(..., description="User ID"),
    language: str = Query(default="EN", description="Language code: EN, RU, UA, DE"),
) -> NextActionResponse:
    lang = language.upper().strip()
    if lang == "UK":  # ISO 639-1 for Ukrainian → internal code
        lang = "UA"
    if lang not in _VALID_LANGUAGES:
        lang = "EN"
    logger.info("[tamagotchi] next-action uid=%d raw_lang=%r resolved_lang=%s", user_id, language, lang)
    return get_next_action(user_id=user_id, language=lang)


@router.post(
    "/tamagotchi/feedback",
    dependencies=[Depends(verify_api_key)],
)
def content_feedback(body: ContentFeedback) -> dict:
    return {"status": "ok"}
