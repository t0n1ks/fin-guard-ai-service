import logging
import random

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query

from app.api.v1.endpoints.analyze import verify_api_key
from app.data.content import ENCOURAGEMENTS
from app.models.response import NextActionResponse
from app.services.tamagotchi_action import get_categorized_content, get_next_action

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_LANGUAGES = {"EN", "RU", "UA", "DE"}
_VALID_CATEGORIES = {"joke", "fact", "advice"}


def _resolve_lang(language: str) -> str:
    lang = language.upper().strip()
    if lang == "UK":
        lang = "UA"
    if lang not in _VALID_LANGUAGES:
        lang = "EN"
    return lang


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
    context: str | None = Query(default=None, description="Budget health hint: good|warn|over"),
) -> NextActionResponse:
    lang = _resolve_lang(language)
    logger.info("[tamagotchi] next-action uid=%d raw_lang=%r resolved_lang=%s ctx=%r", user_id, language, lang, context)
    try:
        return get_next_action(user_id=user_id, language=lang, context=context)
    except Exception:
        logger.exception("[tamagotchi] get_next_action failed — serving local fallback")
        enc = ENCOURAGEMENTS.get(lang, ENCOURAGEMENTS["EN"])
        return NextActionResponse(type="ENCOURAGEMENT", content=random.choice(enc), animation_hint="COIN_COLLECT")


@router.get(
    "/tamagotchi/content",
    response_model=NextActionResponse,
    dependencies=[Depends(verify_api_key)],
)
def categorized_content(
    user_id: int = Query(..., description="User ID"),
    category: str = Query(..., description="Content category: joke, fact, advice"),
    language: str = Query(default="EN", description="Language code: EN, RU, UA, DE"),
    context: str | None = Query(default=None, description="Budget health hint: good|warn|over"),
) -> NextActionResponse:
    """Category-locked content for user-initiated UFO entities (Cow=joke, Star=fact)
    and the transaction-advice path. Returns type="NONE" when the pool is
    exhausted/capped so the frontend can fall back to its local i18n pool."""
    lang = _resolve_lang(language)
    cat = (category or "").strip().lower()
    if cat not in _VALID_CATEGORIES:
        return NextActionResponse(type="NONE", content=None, animation_hint="FLY_BY_MOON")
    logger.info("[tamagotchi] content uid=%d cat=%s lang=%s ctx=%r", user_id, cat, lang, context)
    try:
        return get_categorized_content(user_id=user_id, language=lang, category=cat, context=context)
    except Exception:
        logger.exception("[tamagotchi] get_categorized_content failed — serving NONE")
        return NextActionResponse(type="NONE", content=None, animation_hint="FLY_BY_MOON")


@router.post(
    "/tamagotchi/feedback",
    dependencies=[Depends(verify_api_key)],
)
def content_feedback(body: ContentFeedback) -> dict:
    return {"status": "ok"}
