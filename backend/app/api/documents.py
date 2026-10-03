import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.jobs import JobAlreadyRunning, job_store
from app.models.schemas import DocumentsResponse, DocumentSummary

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_DEPT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.pdf$", re.IGNORECASE)
_RESERVED_DEPTS = {"folders", "library", "upload", "rebuild"}

def _normalize_department(raw: str) -> str:
    name = re.sub(r"[\s]+", "_", raw.strip().lower())
    if not _DEPT_RE.match(name) or name in _RESERVED_DEPTS:
        raise HTTPException(
            status_code=400,
            detail="Folder names may use letters, numbers, '-' and '_' (max 40 chars) and can't be a reserved word.",
        )
    return name


def _dept_dir(settings: Settings, department: str) -> Path:
    root = settings.raw_docs_path.resolve()
    path = (root / department).resolve()
    if path.parent != root:  # blocks ../ tricks
        raise HTTPException(status_code=400, detail="Invalid folder.")
    return path


def _ensure_not_rebuilding() -> None:
    if job_store.is_running("rebuild"):
        raise HTTPException(status_code=409, detail="An index rebuild is running — wait for it to finish.")


def _all_stems(settings: Settings) -> dict[str, str]:
    """document_id (PDF stem) -> department, across the whole library. Document
    ids come from the filename alone, so they must be unique library-wide."""
    root = settings.raw_docs_path
    if not root.exists():
        return {}
    return {p.stem: p.parent.name for p in root.rglob("*.pdf")}


def _read_chunks(settings: Settings, chunking: str) -> list[dict] | None:
    path = settings.chunks_path_for(chunking)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

@router.get("", response_model=DocumentsResponse)
def list_documents(settings: Settings = Depends(get_settings)) -> DocumentsResponse:
    chunks_path = settings.chunks_path_for("fixed")
    if not chunks_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"No ingested documents found at {chunks_path}. "
                "Run scripts/ingest_documents.py first."
            ),
        )

    with chunks_path.open("r", encoding="utf-8") as f:
        chunk_dicts = json.load(f)

    documents: dict[str, dict] = {}
    for chunk in chunk_dicts:
        doc_id = chunk["document_id"]
        if doc_id not in documents:
            documents[doc_id] = {
                "document_id": doc_id,
                "document_name": chunk["document_name"],
                "department": chunk["department"],
                "year": chunk.get("year"),
                "chunk_count": 0,
            }
        documents[doc_id]["chunk_count"] += 1

    return DocumentsResponse(
        documents=[DocumentSummary(**d) for d in documents.values()],
        total_chunks=len(chunk_dicts),
    )

@router.get("/library")
def library(settings: Settings = Depends(get_settings)) -> dict:
    root = settings.raw_docs_path
    fixed_chunks = _read_chunks(settings, "fixed")
    chunk_counts: dict[str, int] = {}
    for c in fixed_chunks or []:
        chunk_counts[c["document_id"]] = chunk_counts.get(c["document_id"], 0) + 1

    fixed_path = settings.chunks_path_for("fixed")
    index_mtime = fixed_path.stat().st_mtime if fixed_path.exists() else None

    departments = []
    on_disk: set[str] = set()
    unindexed: list[str] = []
    changed: list[str] = []
    if root.exists():
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            docs = []
            for pdf in sorted(d.glob("*.pdf")):
                stat = pdf.stat()
                stem = pdf.stem
                on_disk.add(stem)
                in_index = stem in chunk_counts
                if not in_index:
                    status = "not_indexed"
                    unindexed.append(stem)
                elif index_mtime is not None and stat.st_mtime > index_mtime:
                    status = "changed"
                    changed.append(stem)
                else:
                    status = "indexed"
                docs.append(
                    {
                        "document_id": stem,
                        "filename": pdf.name,
                        "department": d.name,
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "status": status,
                        "chunk_count": chunk_counts.get(stem, 0),
                    }
                )
            departments.append({"name": d.name, "documents": docs})

    orphaned = sorted(set(chunk_counts) - on_disk)
    reasons = []
    if unindexed:
        reasons.append(f"{len(unindexed)} new document(s) not indexed yet")
    if changed:
        reasons.append(f"{len(changed)} document(s) changed since the last build")
    if orphaned:
        reasons.append(f"{len(orphaned)} deleted document(s) still in the index")

    return {
        "departments": departments,
        "total_documents": len(on_disk),
        "index": {
            "stale": bool(reasons),
            "reasons": reasons,
            "fixed_built": fixed_path.exists(),
            "semantic_built": settings.chunks_path_for("semantic").exists(),
            "last_built": datetime.fromtimestamp(index_mtime, tz=timezone.utc).isoformat() if index_mtime else None,
            "total_chunks": len(fixed_chunks or []),
        },
        "rebuild_running": job_store.is_running("rebuild"),
    }

class FolderCreate(BaseModel):
    name: str


@router.post("/folders", status_code=201)
def create_folder(body: FolderCreate, settings: Settings = Depends(get_settings)) -> dict:
    _ensure_not_rebuilding()
    name = _normalize_department(body.name)
    path = _dept_dir(settings, name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Folder '{name}' already exists.")
    path.mkdir(parents=True)
    return {"name": name}


@router.delete("/folders/{name}")
def delete_folder(name: str, settings: Settings = Depends(get_settings)) -> dict:
    _ensure_not_rebuilding()
    path = _dept_dir(settings, _normalize_department(name))
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found.")
    if any(path.iterdir()):
        raise HTTPException(status_code=409, detail="Folder isn't empty — delete its documents first.")
    path.rmdir()
    return {"deleted": name}


@router.post("/upload", status_code=201)
def upload_documents(
    department: str = Form(...),
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ensure_not_rebuilding()
    dept = _normalize_department(department)
    target = _dept_dir(settings, dept)

    existing = _all_stems(settings)
    saved: list[dict] = []
    rejected: list[dict] = []

    for upload in files:
        original = Path(upload.filename or "").name
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(original).stem).strip("_").lower()
        reject = lambda reason: rejected.append({"filename": original or "(unnamed)", "reason": reason})  # noqa: E731

        if not original.lower().endswith(".pdf") or not stem:
            reject("Only .pdf files are supported.")
            continue
        if stem in existing:
            reject(
                f"A document with the id '{stem}' already exists in '{existing[stem]}'. "
                "Document ids come from the filename and must be unique — rename the file or delete the old one."
            )
            continue

        data = upload.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            reject(f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
            continue
        if not data.startswith(b"%PDF"):
            reject("This doesn't look like a real PDF.")
            continue

        target.mkdir(parents=True, exist_ok=True)
        (target / f"{stem}.pdf").write_bytes(data)
        existing[stem] = dept
        saved.append({"document_id": stem, "filename": f"{stem}.pdf", "department": dept, "size_bytes": len(data)})

    if not saved and rejected:
        raise HTTPException(status_code=400, detail={"saved": saved, "rejected": rejected})
    return {"saved": saved, "rejected": rejected}


@router.delete("/{department}/{filename}")
def delete_document(department: str, filename: str, settings: Settings = Depends(get_settings)) -> dict:
    _ensure_not_rebuilding()
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid file name.")
    folder = _dept_dir(settings, department)
    path = (folder / filename).resolve()
    if path.parent != folder or not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found.")
    path.unlink()
    return {"deleted": filename}

class RebuildRequest(BaseModel):
    chunking: list[str] | None = None


@router.post("/rebuild", status_code=202)
def rebuild(body: RebuildRequest | None = None, settings: Settings = Depends(get_settings)) -> dict:
    from app.ingestion.index_builder import rebuild_index

    chunking = (body.chunking if body else None) or ["fixed", "semantic"]
    bad = [c for c in chunking if c not in ("fixed", "semantic")]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown chunking strategy: {bad}")
    try:
        return job_store.start("rebuild", lambda report: rebuild_index(report, chunking, settings))
    except JobAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc