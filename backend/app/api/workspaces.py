"""
/workspaces — the sample vs. private workspaces.

  POST   /workspaces            create a private workspace (optionally pre-filled with a copy of the sample)
  GET    /workspaces/current    what the caller is looking at: sample or private, limits, expiry, key status
  DELETE /workspaces/{id}       delete your own private workspace (the id in the path must be the one you send)
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import SAMPLE_WORKSPACE, Settings, get_settings
from app.core.workspaces import (
    create_workspace,
    delete_workspace,
    expires_at,
    requested_workspace_id,
    usage,
    workspace_settings,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    copy_sample: bool = False


def _client(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("", status_code=201)
def create(request: Request, body: WorkspaceCreate | None = None, base: Settings = Depends(get_settings)) -> dict:
    return create_workspace(base, copy_sample=bool(body and body.copy_sample), client=_client(request))


@router.get("/current")
def current(settings: Settings = Depends(workspace_settings)) -> dict:
    used = usage(settings)
    limited = not settings.is_sample
    expiry = expires_at(settings, settings.workspace_id)
    return {
        "id": settings.workspace_id,
        "is_sample": settings.is_sample,
        "read_only": settings.workspace_read_only,
        "mode": settings.app_mode,
        "expires_at": expiry,
        "expires_in_days": round((expiry - time.time()) / 86400, 1) if expiry else None,
        "ttl_days": settings.workspace_ttl_days,
        "usage": {"documents": used["documents"], "megabytes": round(used["bytes"] / (1024 * 1024), 1)},
        "limits": {
            "documents": settings.max_docs_per_workspace,
            "megabytes": settings.max_workspace_mb,
            "upload_megabytes": settings.max_upload_mb,
            "questions": settings.max_questions_per_workspace,
        } if limited else None,
        "model": {
            "current": settings.groq_model,
            "default": settings.default_groq_model or settings.groq_model,
            "options": settings.model_choices,
            "custom_allowed": settings.allow_custom_model and (settings.user_supplied_key or not settings.is_hosted),
        },
        "key": {
            "server_key_allowed": settings.server_key_allowed,
            "using_your_key": settings.user_supplied_key,
            "can_use_llm": bool(settings.groq_api_key),
        },
    }


@router.delete("/{workspace_id}")
def remove(workspace_id: str, request: Request, base: Settings = Depends(get_settings)) -> dict:
    caller = requested_workspace_id(request)
    if workspace_id == SAMPLE_WORKSPACE or caller != workspace_id:
        raise HTTPException(status_code=403, detail="You can only delete your own private workspace.")
    delete_workspace(base, workspace_id)
    return {"deleted": workspace_id}
