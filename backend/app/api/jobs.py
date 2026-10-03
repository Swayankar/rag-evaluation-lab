from fastapi import APIRouter, HTTPException

from app.core.jobs import job_store

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(kind: str | None = None) -> dict:
    """Newest first. The UI uses this to re-attach to a running rebuild after a page refresh."""
    return {"jobs": job_store.list(kind)}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job (jobs are kept in memory and lost on restart).")
    return job
