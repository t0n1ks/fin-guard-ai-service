import logging
import sys
import time

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.api.v1.endpoints.analyze import router as analyze_router
from app.api.v1.endpoints.tamagotchi import router as tamagotchi_router
from app.core.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
# force=True overwrites any handler uvicorn already installed so everything
# ends up on the same stdout stream that Render captures.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="FinGuard AI Brain", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    logger.info("%s %s → %d  (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    return response


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
