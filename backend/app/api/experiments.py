"""
GET /experiments — read-only access to the comparison results
scripts/compare_experiments.py already produced on disk.
"""
import json
import re

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/experiments", tags=["experiments"])

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


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
    with comparison_path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    with detail_path.open("r", encoding="utf-8") as f:
        return json.load(f)