import logging

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api.v1.endpoints.analyze import router as analyze_router
from app.api.v1.endpoints.tamagotchi import router as tamagotchi_router
from app.core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="FinGuard AI Brain", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(analyze_router, prefix="/v1")
app.include_router(tamagotchi_router, prefix="/v1")


@app.get("/health")
def health():
    from app.services.content_tracker import _USE_DB
    return {
        "status": "ok",
        "maintenance_mode": settings.maintenance_mode,
        "storage": "postgresql" if _USE_DB else "file",
    }


if __name__ == "__main__":
    logger.info("FinGuard AI Brain starting on port %s", settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )
