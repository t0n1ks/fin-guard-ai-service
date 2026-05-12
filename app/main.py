import logging
import sys
import time

print("[1/6] FinGuard AI Brain — startup begin", flush=True)

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()
print("[2/6] Env loaded", flush=True)

from app.core.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)
logger.info("[3/6] Config ready — port=%s maintenance=%s", settings.port, settings.maintenance_mode)

# ── App + health (defined before heavy router imports) ────────────────────────
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


@app.get("/health")
def health():
    from app.services.content_tracker import _USE_DB, _DB_URL
    db_connected: bool | None = None
    if _USE_DB:
        try:
            import psycopg2
            with psycopg2.connect(_DB_URL, connect_timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            db_connected = True
        except Exception as exc:
            logger.warning("health: DB connectivity check failed: %s", exc)
            db_connected = False
    return {
        "status": "ok",
        "maintenance_mode": settings.maintenance_mode,
        "storage": "postgresql" if _USE_DB else "file",
        "db_connected": db_connected,
    }


# ── Routers (heavy imports: sklearn + background DB init) ─────────────────────
logger.info("[4/6] Importing routers (sklearn + services)…")

from app.api.v1.endpoints.analyze import router as analyze_router
from app.api.v1.endpoints.tamagotchi import router as tamagotchi_router

logger.info("[5/6] Routers imported")

app.include_router(analyze_router, prefix="/v1")
app.include_router(tamagotchi_router, prefix="/v1")

logger.info("[6/6] Startup complete — uvicorn binding on port %s", settings.port)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )
