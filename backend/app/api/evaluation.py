"""
/evaluation — edit the question set, run evaluations, read saved results.

  GET    /evaluation/questions          the current questions.json (+ known document ids)
  PUT    /evaluation/questions          replace the whole question set
  POST   /evaluation/run                start a background run -> poll GET /jobs/{id}
  GET    /evaluation/results            every saved result (aggregates + meta)
  GET    /evaluation/results/{name}     one result with per-question detail
  DELETE /evaluation/results/{name}     remove a saved result
"""
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.jobs import JobAlreadyRunning, JobCapacityReached, job_store
from app.core.workspaces import NO_KEY_MESSAGE, key_missing, workspace_settings
from app.evaluation.dataset import EvalDataset, EvalQuestion, load_eval_dataset
from app.evaluation.job import dataset_hash, run_evaluation_job, write_json_atomic
from app.models.schemas import StrategyChoice

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _known_document_ids(settings: Settings) -> list[str]:
    root = settings.raw_docs_path
    return sorted({p.stem for p in root.rglob("*.pdf")}) if root.exists() else []


def _load(settings: Settings) -> EvalDataset | None:
    path = settings.eval_dataset_path
    if not path.exists():
        return None
    try:
        return load_eval_dataset(path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"{path} couldn't be parsed: {exc}") from exc


# --------------------------------------------------------------------------
# questions
# --------------------------------------------------------------------------

@router.get("/questions")
def get_questions(settings: Settings = Depends(workspace_settings)) -> dict:
    dataset = _load(settings)
    return {
        "exists": dataset is not None,
        "questions": [q.model_dump() for q in dataset.questions] if dataset else [],
        "dataset_hash": dataset_hash(dataset) if dataset else None,
        "known_document_ids": _known_document_ids(settings),
    }


def _clean(dataset: EvalDataset) -> tuple[list[EvalQuestion], list[str]]:
    problems: list[str] = []
    cleaned: list[EvalQuestion] = []
    seen: set[str] = set()
    for i, q in enumerate(dataset.questions, start=1):
        qid = q.id.strip()
        text = q.question.strip()
        label = f"Question {i}" + (f" ({qid})" if qid else "")
        if not qid:
            problems.append(f"Question {i}: id is empty.")
        elif qid in seen:
            problems.append(f"{label}: duplicate id.")
        seen.add(qid)
        if not text:
            problems.append(f"{label}: question text is empty.")
        docs = list(dict.fromkeys(d.strip() for d in q.relevant_document_ids if d.strip()))
        if not docs:
            problems.append(f"{label}: pick at least one relevant document.")
        cleaned.append(
            EvalQuestion(
                id=qid,
                question=text,
                relevant_document_ids=docs,
                expected_answer=(q.expected_answer or "").strip() or None,
                expected_keywords=[k.strip() for k in q.expected_keywords if k.strip()],
                category=(q.category or "").strip() or None,
            )
        )
    return cleaned, problems


@router.put("/questions")
def put_questions(dataset: EvalDataset, settings: Settings = Depends(workspace_settings)) -> dict:
    cleaned, problems = _clean(dataset)
    if not settings.is_sample and len(cleaned) > settings.max_questions_per_workspace:
        problems.append(f"A private workspace holds at most {settings.max_questions_per_workspace} questions.")
    if problems:
        raise HTTPException(status_code=422, detail=" ".join(problems))

    known = set(_known_document_ids(settings))
    warnings = [
        f"{q.id}: '{d}' isn't a document in the library (recall for this question will be 0)."
        for q in cleaned
        for d in q.relevant_document_ids
        if d not in known
    ]
    saved = EvalDataset(questions=cleaned)
    write_json_atomic(settings.eval_dataset_path, {"questions": [q.model_dump() for q in cleaned]})
    return {"saved": len(cleaned), "dataset_hash": dataset_hash(saved), "warnings": warnings}


# --------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------

class EvaluationRunRequest(BaseModel):
    strategies: list[StrategyChoice] = Field(..., min_length=1, max_length=8)
    top_k: int = Field(default=5, ge=1, le=20)
    run_llm_judges: bool = True


@router.post("/run", status_code=202)
def run_evaluation(body: EvaluationRunRequest, settings: Settings = Depends(workspace_settings)) -> dict:
    dataset = _load(settings)
    if dataset is None or len(dataset) == 0:
        raise HTTPException(status_code=400, detail="There are no evaluation questions yet — add some first.")
    if key_missing(settings):
        raise HTTPException(status_code=400, detail=NO_KEY_MESSAGE)
    if job_store.is_running("rebuild", settings.workspace_id):
        raise HTTPException(status_code=409, detail="An index rebuild is running — wait for it to finish.")
    if job_store.is_running("experiments", settings.workspace_id):
        raise HTTPException(status_code=409, detail="An experiment run is in progress — wait for it to finish.")

    combos = list(dict.fromkeys((s.chunking_strategy, s.retrieval_strategy) for s in body.strategies))
    try:
        return job_store.start(
            "evaluation",
            lambda report: run_evaluation_job(report, combos, body.top_k, dataset, settings, body.run_llm_judges),
            owner=settings.workspace_id,
            max_active=settings.max_concurrent_jobs,
        )
    except JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobCapacityReached as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------

def _split_name(name: str) -> tuple[str | None, str | None]:
    for chunking in ("fixed", "semantic"):
        if name.startswith(f"{chunking}_"):
            return chunking, name[len(chunking) + 1 :]
    return None, None


@router.get("/results")
def list_results(settings: Settings = Depends(workspace_settings)) -> dict:
    dataset = _load(settings)
    current = dataset_hash(dataset) if dataset else None

    items = []
    directory = settings.eval_results_dir
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        meta = data.get("meta") or {}
        chunking, retrieval = _split_name(path.stem)
        items.append(
            {
                "name": path.stem,
                "chunking": chunking,
                "retrieval": retrieval,
                "aggregate": data.get("aggregate", {}),
                "meta": meta,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "dataset_match": (meta.get("dataset_hash") == current) if meta.get("dataset_hash") and current else None,
            }
        )
    return {"results": items, "current_dataset_hash": current}


@router.get("/results/{name}")
def get_result(name: str, settings: Settings = Depends(workspace_settings)) -> dict:
    if not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid result name.")
    path = settings.eval_results_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No saved result named {name!r}.")
    return json.loads(path.read_text(encoding="utf-8"))


@router.delete("/results/{name}")
def delete_result(name: str, settings: Settings = Depends(workspace_settings)) -> dict:
    if not _SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid result name.")
    path = settings.eval_results_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No saved result named {name!r}.")
    path.unlink()
    return {"deleted": name}
