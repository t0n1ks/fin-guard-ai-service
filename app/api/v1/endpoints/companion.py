import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.endpoints.analyze import verify_api_key
from app.services.companion_renderer import render_message

router = APIRouter()
logger = logging.getLogger(__name__)

_LANGUAGES = {"en", "de", "ru", "uk"}


class CompanionRenderRequest(BaseModel):
    user_id: int
    type: str
    tone: str = "supportive"
    language: str = "en"
    currency: str = ""
    slots: dict[str, Any] = Field(default_factory=dict)


class CompanionRenderResponse(BaseModel):
    text: Optional[str] = None  # None → the client uses its own fallback


@router.post(
    "/companion/render",
    response_model=CompanionRenderResponse,
    dependencies=[Depends(verify_api_key)],
)
def render(body: CompanionRenderRequest) -> CompanionRenderResponse:
    """Word a companion message Go has already chosen (type + numbers)."""
    lang = body.language.lower().strip()
    if lang == "ua":
        lang = "uk"
    if lang not in _LANGUAGES:
        lang = "en"
    text = render_message(body.user_id, body.type, body.tone, lang, body.slots, body.currency)
    logger.info("[companion] render uid=%d type=%s lang=%s hit=%s", body.user_id, body.type, lang, text is not None)
    return CompanionRenderResponse(text=text)
