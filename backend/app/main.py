from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import config, documents, evaluation, experiments, jobs, query
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="RAG Evaluation Lab API",
    version="0.3.0",
    description="/query, /documents, /experiments, /evaluation, /jobs and /config over the RAG Evaluation Lab pipeline.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)
app.include_router(documents.router)
app.include_router(evaluation.router)
app.include_router(experiments.router)
app.include_router(evaluation.router)
app.include_router(jobs.router)
app.include_router(config.router)


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
