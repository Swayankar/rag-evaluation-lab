import json

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.models.schemas import DocumentsResponse, DocumentSummary

router = APIRouter(prefix="/documents", tags=["documents"])


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