from fastapi import FastAPI
from app.api.v1.endpoints.analyze import router as analyze_router

app = FastAPI(title="FinGuard AI Brain", version="1.0.0")

app.include_router(analyze_router, prefix="/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
