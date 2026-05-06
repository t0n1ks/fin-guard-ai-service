from fastapi import APIRouter, Depends, Query

from app.api.v1.endpoints.analyze import verify_api_key
from app.models.response import NextActionResponse
from app.services.tamagotchi_action import get_next_action

router = APIRouter()

_VALID_LANGUAGES = {"EN", "RU", "UA", "DE"}


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
    if lang not in _VALID_LANGUAGES:
        lang = "EN"
    return get_next_action(user_id=user_id, language=lang)
