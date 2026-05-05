import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.api.v1.endpoints.analyze import router as analyze_router
from app.core.config import settings

app = FastAPI(title="FinGuard AI Brain", version="1.0.0")

app.include_router(analyze_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )
