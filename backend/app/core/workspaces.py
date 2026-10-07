import re
import secrets
import shutil
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from app.core.config import SAMPLE_WORKSPACE, Settings, get_settings
from app.core.jobs import job_store
from app.core.logging import get_logger

logger = get_logger(__name__)

WORKSPACE_HEADER = "X-Workspace"
KEY_HEADER = "X-Groq-Key"
MODEL_HEADER = "X-Groq-Model"
_ID_RE = re.compile(r"^[a-f0-9]{20}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{8,256}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,99}$")
_MARKER = ".last_used"

NO_KEY_MESSAGE = (
    "A Groq API key is needed to run this. Paste yours in the key box (it stays in your browser "
    "and is only sent to this server to call Groq on your behalf)."
)

# Non-GET requests that are fine on the read-only sample: they only READ the data.
_SAMPLE_WRITE_ALLOWLIST = ("/query", "/workspaces")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_touch_lock = threading.Lock()
_last_touched: dict[str, float] = {}
_create_log: dict[str, deque] = defaultdict(deque)
_create_lock = threading.Lock()


# --------------------------------------------------------------------------
# paths / ids
# --------------------------------------------------------------------------

def workspaces_root(base: Settings) -> Path:
    return Path(base.workspaces_dir).resolve()


def workspace_dir(base: Settings, workspace_id: str) -> Path:
    if not _ID_RE.match(workspace_id):
        raise HTTPException(status_code=400, detail="Invalid workspace id.")
    return workspaces_root(base) / workspace_id


def requested_workspace_id(request: Request) -> str:
    """The id the caller asked for (not yet checked to exist). Missing = the sample."""
    raw = (request.headers.get(WORKSPACE_HEADER) or "").strip().lower()
    if not raw or raw == SAMPLE_WORKSPACE:
        return SAMPLE_WORKSPACE
    if not _ID_RE.match(raw):
        raise HTTPException(status_code=400, detail="Invalid workspace id.")
    return raw


def _touch(path: Path, workspace_id: str) -> None:
    """Record activity (throttled: at most one disk write a minute per workspace)."""
    now = time.time()
    with _touch_lock:
        if now - _last_touched.get(workspace_id, 0) < 60:
            return
        _last_touched[workspace_id] = now
    try:
        (path / _MARKER).touch()
    except OSError:
        pass


def _last_used(path: Path) -> float:
    marker = path / _MARKER
    try:
        return (marker if marker.exists() else path).stat().st_mtime
    except OSError:
        return 0.0


# --------------------------------------------------------------------------
# request dependencies
# --------------------------------------------------------------------------

def workspace_settings(request: Request, base: Settings = Depends(get_settings)) -> Settings:
    """Settings for THIS request: the workspace it names + the caller's Groq key."""
    workspace_id = requested_workspace_id(request)

    user_key = (request.headers.get(KEY_HEADER) or "").strip()
    if user_key and not _KEY_RE.match(user_key):
        raise HTTPException(status_code=400, detail="That doesn't look like a valid Groq API key.")
    if user_key:
        key, user_supplied = user_key, True
    else:
        key, user_supplied = (base.groq_api_key if base.server_key_allowed else ""), False

    model = (request.headers.get(MODEL_HEADER) or "").strip()
    if model:
        if not _MODEL_RE.match(model):
            raise HTTPException(status_code=400, detail="That doesn't look like a valid model name.")
        if model not in base.model_choices:
            custom_ok = base.allow_custom_model and (user_supplied or not base.is_hosted)
            if not custom_ok:
                raise HTTPException(
                    status_code=400,
                    detail="Pick one of the listed models"
                    + ("" if user_supplied else " (custom model names need your own Groq key)")
                    + ".",
                )
    chosen = model or base.groq_model

    update: dict = {"groq_model": chosen, "default_groq_model": base.groq_model, "model_overridden": chosen != base.groq_model, "groq_api_key": key, "user_supplied_key": user_supplied, "workspace_id": workspace_id}
    if base.is_hosted:
        update.update(langchain_tracing_v2=False, langchain_api_key="")

    if workspace_id == SAMPLE_WORKSPACE:
        update["workspace_read_only"] = base.is_hosted
        return base.model_copy(update=update)

    path = workspace_dir(base, workspace_id)
    if not path.is_dir():
        raise HTTPException(
            status_code=410,
            detail="This private workspace no longer exists (private workspaces are deleted after "
            f"{base.workspace_ttl_days} idle days). Start a new one, or go back to the sample.",
        )
    _touch(path, workspace_id)
    update.update(base.paths_for_workspace(workspace_id))
    update["workspace_read_only"] = False
    return base.model_copy(update=update)


def write_guard(request: Request, base: Settings = Depends(get_settings)) -> None:
    """Global dependency: nobody may modify the hosted sample. Default-deny."""
    if request.method in _SAFE_METHODS or not base.is_hosted:
        return
    if requested_workspace_id(request) != SAMPLE_WORKSPACE:
        return
    path = request.url.path
    if any(path == p or path.startswith(p + "/") for p in _SAMPLE_WRITE_ALLOWLIST):
        return
    raise HTTPException(
        status_code=403,
        detail="The sample workspace is read-only. Start your own private workspace to upload documents, "
        "edit questions, or run evaluations.",
    )


def key_missing(settings: Settings) -> bool:
    """True when this caller has no usable key AND may not fall back to the server's."""
    return not settings.groq_api_key and not settings.server_key_allowed


# --------------------------------------------------------------------------
# limits
# --------------------------------------------------------------------------

def usage(settings: Settings) -> dict:
    root = settings.raw_docs_path
    pdfs = list(root.rglob("*.pdf")) if root.exists() else []
    return {"documents": len(pdfs), "bytes": sum(p.stat().st_size for p in pdfs)}


def enforce_upload_limits(settings: Settings, incoming_bytes: int) -> None:
    """Private workspaces only (the sample has no limits in local mode)."""
    if settings.is_sample:
        return
    used = usage(settings)
    if used["documents"] + 1 > settings.max_docs_per_workspace:
        raise HTTPException(
            status_code=413,
            detail=f"A private workspace holds at most {settings.max_docs_per_workspace} documents — delete one first.",
        )
    if used["bytes"] + incoming_bytes > settings.max_workspace_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"A private workspace holds at most {settings.max_workspace_mb} MB of documents.",
        )


# --------------------------------------------------------------------------
# create / delete / reap
# --------------------------------------------------------------------------

def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _check_creation_rate(base: Settings, client: str) -> None:
    limit = base.max_workspaces_per_ip_per_hour
    if limit <= 0:
        return
    now = time.time()
    with _create_lock:
        log = _create_log[client]
        while log and now - log[0] > 3600:
            log.popleft()
        if len(log) >= limit:
            raise HTTPException(status_code=429, detail="Too many new workspaces from your network — try again later.")
        log.append(now)


def list_ids(base: Settings) -> list[str]:
    root = workspaces_root(base)
    return sorted(p.name for p in root.iterdir() if p.is_dir() and _ID_RE.match(p.name)) if root.exists() else []


def create_workspace(base: Settings, copy_sample: bool = False, client: str = "local") -> dict:
    _check_creation_rate(base, client)
    reap_expired(base)
    if len(list_ids(base)) >= base.max_workspaces:
        raise HTTPException(
            status_code=503,
            detail="The server is at its limit of private workspaces right now. Try again later, "
            "or keep browsing the sample.",
        )

    workspace_id = secrets.token_hex(10)
    paths = base.paths_for_workspace(workspace_id)
    root = workspace_dir(base, workspace_id)
    for p in paths.values():
        Path(p).mkdir(parents=True, exist_ok=True)
    (root / _MARKER).touch()

    copied = False
    if copy_sample:
        sample = base.model_copy(update={"workspace_id": SAMPLE_WORKSPACE})
        try:
            _copy_if_exists(sample.raw_docs_path, Path(paths["raw_docs_dir"]))
            _copy_if_exists(sample.processed_chunks_path, Path(paths["processed_chunks_dir"]))
            target = base.model_copy(update=paths)
            for chunking in ("fixed", "semantic"):
                _copy_if_exists(sample.vector_store_path_for(chunking), target.vector_store_path_for(chunking))
            _copy_if_exists(sample.eval_dataset_path, Path(paths["eval_dataset_dir"]) / "questions.json")
            exp_dir = Path(sample.experiments_dir)
            for f in exp_dir.glob("experiment_*.json") if exp_dir.exists() else []:
                shutil.copy2(f, Path(paths["experiments_dir"]) / f.name)
            copied = True
        except OSError:
            logger.exception("Copying the sample into %s failed", workspace_id)
            shutil.rmtree(root, ignore_errors=True)
            raise HTTPException(status_code=500, detail="Couldn't copy the sample into your workspace.")

    logger.info("Created workspace %s (copy_sample=%s)", workspace_id, copied)
    return {"id": workspace_id, "copied_sample": copied, "ttl_days": base.workspace_ttl_days}


def delete_workspace(base: Settings, workspace_id: str) -> None:
    from app.core.dependencies import clear_pipeline_cache

    path = workspace_dir(base, workspace_id)
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="No such workspace.")
    if job_store.owner_busy(workspace_id):
        raise HTTPException(status_code=409, detail="A job is running in this workspace — wait for it to finish.")
    clear_pipeline_cache(workspace_id)
    shutil.rmtree(path, ignore_errors=True)
    with _touch_lock:
        _last_touched.pop(workspace_id, None)
    logger.info("Deleted workspace %s", workspace_id)


def reap_expired(base: Settings) -> list[str]:
    """Delete private workspaces idle longer than the TTL. Returns the deleted ids."""
    cutoff = time.time() - base.workspace_ttl_days * 86400
    deleted = []
    for workspace_id in list_ids(base):
        path = workspaces_root(base) / workspace_id
        if _last_used(path) < cutoff and not job_store.owner_busy(workspace_id):
            try:
                delete_workspace(base, workspace_id)
                deleted.append(workspace_id)
            except HTTPException:
                continue
    return deleted


def start_reaper(interval_seconds: int = 3600) -> threading.Thread:
    def loop() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                reap_expired(get_settings())
            except Exception:
                logger.exception("Workspace cleanup failed")

    thread = threading.Thread(target=loop, daemon=True, name="workspace-reaper")
    thread.start()
    return thread


def expires_at(base: Settings, workspace_id: str) -> float | None:
    if workspace_id == SAMPLE_WORKSPACE:
        return None
    return _last_used(workspaces_root(base) / workspace_id) + base.workspace_ttl_days * 86400
