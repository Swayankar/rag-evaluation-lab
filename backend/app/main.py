from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents, query
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="RAG Evaluation Lab API",
    version="0.1.0",
    description="Phase 4: /query and /documents over the Phase 1-3 pipeline.",
)

# Wide open for local dev / the Phase 10 frontend. Tighten allow_origins
# once there's a real frontend origin to lock this down to.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)
app.include_router(documents.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
