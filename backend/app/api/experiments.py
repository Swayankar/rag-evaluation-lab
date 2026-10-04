import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.jobs import JobAlreadyRunning, job_store
from app.evaluation.dataset import load_eval_dataset
from app.evaluation.job import dataset_hash, write_json_atomic
from app.experiments.recommend import recommend
from app.experiments.registry import CANONICAL_EXPERIMENTS, _from_dict, _to_dict
from app.models.schemas import ChunkingName, RetrievalName

router = APIRouter(prefix="/experiments", tags=["experiments"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_RESERVED_NAMES = {"comparison_latest", "overview", "configs", "run"}
MAX_EXPERIMENTS = 12


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _current_dataset_hash(settings: Settings) -> str | None:
    path = settings.eval_dataset_path
    if not path.exists():
        return None
    try:
        return dataset_hash(load_eval_dataset(path))
    except Exception:
        return None


# --------------------------------------------------------------------------
# existing read-only endpoints (behaviour unchanged)
# --------------------------------------------------------------------------

@router.get("")
def list_experiments(settings: Settings = Depends(get_settings)) -> dict:
    comparison_path = settings.experiments_results_dir / "comparison_latest.json"
    if not comparison_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"No experiment comparison found at {comparison_path}. "
                "Run scripts/compare_experiments.py first."
            ),
        )
    return _load_json(comparison_path)


# --------------------------------------------------------------------------
# overview
# --------------------------------------------------------------------------

@router.get("/overview")
def overview(settings: Settings = Depends(get_settings)) -> dict:
    path = settings.experiments_results_dir / "comparison_latest.json"
    comparison = None
    if path.exists():
        try:
            comparison = _load_json(path)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{path} couldn't be parsed: {exc}") from exc

    current = _current_dataset_hash(settings)
    saved = ((comparison or {}).get("meta") or {}).get("dataset_hash")
    return {
        "comparison": comparison,
        "recommendation": recommend(comparison),
        "current_dataset_hash": current,
        # None = unknown (the CLI script's output carries no dataset hash)
        "dataset_match": (saved == current) if saved and current else None,
        "running": job_store.is_running("experiments"),
    }


# --------------------------------------------------------------------------
# experiment definitions
# --------------------------------------------------------------------------

class ExperimentConfigIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    chunking_strategy: ChunkingName = "fixed"
    retrieval_strategy: RetrievalName = "vector"
    top_k: int = Field(default=5, ge=1, le=20)


class ConfigsIn(BaseModel):
    experiments: list[ExperimentConfigIn] = Field(..., min_length=1, max_length=MAX_EXPERIMENTS)


def _read_configs(settings: Settings) -> tuple[list[dict], list[str], bool]:
    """(configs, problems, from_files). Falls back to the canonical five when
    the directory has no experiment_*.json yet, like the CLI script does."""
    directory = Path(settings.experiments_dir)
    files = sorted(directory.glob("experiment_*.json")) if directory.exists() else []
    if not files:
        return [_to_dict(c) for c in CANONICAL_EXPERIMENTS], [], False

    configs, problems = [], []
    for f in files:
        try:
            configs.append({**_to_dict(_from_dict(_load_json(f))), "file": f.name})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"{f.name}: {type(exc).__name__}: {exc}")
    return configs, problems, True


@router.get("/configs")
def get_configs(settings: Settings = Depends(get_settings)) -> dict:
    configs, problems, from_files = _read_configs(settings)
    return {
        "experiments": configs,
        "from_files": from_files,
        "problems": problems,
        "canonical": [_to_dict(c) for c in CANONICAL_EXPERIMENTS],
        "directory": str(Path(settings.experiments_dir)),
    }


@router.put("/configs")
def put_configs(body: ConfigsIn, settings: Settings = Depends(get_settings)) -> dict:
    problems: list[str] = []
    seen: set[str] = set()
    for i, cfg in enumerate(body.experiments, start=1):
        if not _SAFE_NAME_RE.match(cfg.name):
            problems.append(f"Experiment {i}: name '{cfg.name}' may only use letters, numbers, '_' and '-'.")
        elif cfg.name in _RESERVED_NAMES:
            problems.append(f"Experiment {i}: '{cfg.name}' is a reserved name.")
        elif cfg.name in seen:
            problems.append(f"Experiment {i}: duplicate name '{cfg.name}'.")
        seen.add(cfg.name)
    if problems:
        raise HTTPException(status_code=422, detail=" ".join(problems))
    if job_store.is_running("experiments"):
        raise HTTPException(status_code=409, detail="An experiment run is in progress — wait for it to finish.")

    directory = Path(settings.experiments_dir)
    written = []
    for i, cfg in enumerate(body.experiments, start=1):
        path = directory / f"experiment_{i:03d}.json"
        write_json_atomic(path, {"name": cfg.name, "chunking_strategy": cfg.chunking_strategy,
                                 "retrieval_strategy": cfg.retrieval_strategy, "top_k": cfg.top_k})
        written.append(path.name)
    for stale in directory.glob("experiment_*.json"):
        if stale.name not in written:
            stale.unlink()
    return {"saved": len(written), "files": written}


# --------------------------------------------------------------------------
# running
# --------------------------------------------------------------------------

class RunRequest(BaseModel):
    run_llm_judges: bool = True


@router.post("/run", status_code=202)
def run_experiments(body: RunRequest | None = None, settings: Settings = Depends(get_settings)) -> dict:
    path = settings.eval_dataset_path
    if not path.exists():
        raise HTTPException(status_code=400, detail="There are no evaluation questions yet — add some on the Evaluation page.")
    try:
        dataset = load_eval_dataset(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"{path} couldn't be parsed: {exc}") from exc
    if len(dataset) == 0:
        raise HTTPException(status_code=400, detail="There are no evaluation questions yet — add some on the Evaluation page.")
    if job_store.is_running("rebuild"):
        raise HTTPException(status_code=409, detail="An index rebuild is running — wait for it to finish.")
    if job_store.is_running("evaluation"):
        raise HTTPException(status_code=409, detail="An evaluation run is in progress — wait for it to finish.")

    from app.experiments.job import run_experiments_job  # lazy: pulls in the pipeline stack
    from app.experiments.registry import load_experiment_configs

    strategies = load_experiment_configs(Path(settings.experiments_dir))
    judges = body.run_llm_judges if body else True
    try:
        return job_store.start(
            "experiments",
            lambda report: run_experiments_job(report, strategies, dataset, settings, judges),
        )
    except JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# one experiment's detail (declared last: it would swallow the fixed paths above)
# --------------------------------------------------------------------------

@router.get("/{experiment_name}")
def get_experiment_detail(experiment_name: str, settings: Settings = Depends(get_settings)) -> dict:
    if not _SAFE_NAME_RE.match(experiment_name):
        raise HTTPException(status_code=400, detail="Invalid experiment name.")

    detail_path = settings.experiments_results_dir / f"{experiment_name}.json"
    if not detail_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No experiment named {experiment_name!r} found at {detail_path}.",
        )
    return _load_json(detail_path)
