import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chunking.fixed_chunker import FixedChunker
from app.models.document import RawPage


def _make_page(document_id: str, page: int, word_count: int) -> RawPage:
    text = " ".join(f"word{i}" for i in range(word_count))
    return RawPage(
        document_id=document_id,
        document_name=document_id.replace("_", " ").title(),
        department="hr",
        page=page,
        text=text,
    )


def test_fixed_chunker_produces_overlapping_chunks():
    pages = [_make_page("vacation_policy", 1, 1200)]
    chunker = FixedChunker(chunk_size=500, overlap=50)

    chunks = chunker.chunk_pages(pages)

    assert len(chunks) > 1
    assert all(c.chunking_strategy == "fixed" for c in chunks)
    assert all(c.document_id == "vacation_policy" for c in chunks)
    # chunk_index should be sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_fixed_chunker_handles_multiple_documents_independently():
    pages = [
        _make_page("doc_a", 1, 600),
        _make_page("doc_b", 1, 600),
    ]
    chunker = FixedChunker(chunk_size=500, overlap=50)

    chunks = chunker.chunk_pages(pages)
    doc_ids = {c.document_id for c in chunks}

    assert doc_ids == {"doc_a", "doc_b"}
    # chunk_index restarts at 0 for each document
    for doc_id in doc_ids:
        indices = [c.chunk_index for c in chunks if c.document_id == doc_id]
        assert indices[0] == 0


def test_fixed_chunker_empty_input_returns_no_chunks():
    chunker = FixedChunker()
    assert chunker.chunk_pages([]) == []


if __name__ == "__main__":
    test_fixed_chunker_produces_overlapping_chunks()
    test_fixed_chunker_handles_multiple_documents_independently()
    test_fixed_chunker_empty_input_returns_no_chunks()
    print("✅ All chunking tests passed.")
