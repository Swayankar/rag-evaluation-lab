from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings
from app.core.jobs import job_store
from app.core.workspaces import workspace_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(kind: str | None = None, settings: Settings = Depends(workspace_settings)) -> dict:
    """Newest first, THIS workspace's jobs only. The UI uses this to re-attach to a running job after a refresh."""
    return {"jobs": job_store.list(kind, owner=settings.workspace_id)}


@router.get("/{job_id}")
def get_job(job_id: str, settings: Settings = Depends(workspace_settings)) -> dict:
    job = job_store.get(job_id, owner=settings.workspace_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job (jobs are kept in memory and lost on restart).")
    return job
