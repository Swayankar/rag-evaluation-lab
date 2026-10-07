from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import config, documents, evaluation, experiments, jobs, query, workspaces
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.workspaces import start_reaper, write_guard

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Hourly sweep that deletes private workspaces idle longer than the TTL.
    start_reaper()
    yield


app = FastAPI(
    title="RAG Evaluation Lab API",
    version="0.4.0",
    description="/query, /documents, /experiments, /evaluation, /jobs, /config and /workspaces over the RAG Evaluation Lab pipeline.",
    lifespan=lifespan,
    # Default-deny: in hosted mode nothing may modify the shared sample workspace.
    dependencies=[Depends(write_guard)],
)

_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],  # includes X-Workspace and X-Groq-Key
)

@app.middleware("http")
async def never_cache(request: Request, call_next):
    """Every response depends on WHO is asking (workspace + key), so no browser or CDN may reuse one
    for a different caller or after the workspace changed."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "X-Workspace, X-Groq-Key"
    return response


app.include_router(query.router)
app.include_router(documents.router)
app.include_router(evaluation.router)
app.include_router(experiments.router)
app.include_router(jobs.router)
app.include_router(config.router)
app.include_router(workspaces.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
