import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chunking.semantic_chunker import SemanticChunker, split_sentences
from app.embeddings.embedder import HashingEmbedder
from app.models.document import RawPage


def _make_page(document_id: str, page: int, text: str) -> RawPage:
    return RawPage(
        document_id=document_id,
        document_name=document_id.replace("_", " ").title(),
        department="hr",
        page=page,
        text=text,
    )

def test_split_sentences_basic():
    text = "Employees are eligible after six months. Leave lasts sixteen weeks. Apply via HR."
    sentences = split_sentences(text)
    assert sentences == [
        "Employees are eligible after six months.",
        "Leave lasts sixteen weeks.",
        "Apply via HR.",
    ]


def test_split_sentences_handles_empty_text():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_semantic_chunker_produces_chunks_from_multiple_sentences():
    # Repeat two distinct "topics" enough times that the hashing embedder
    # (bag-of-words) can actually tell them apart via word overlap.
    eligibility = "Employees must complete six months of continuous service to qualify. " * 3
    duration = "Approved leave lasts up to sixteen weeks after the birth of a child. " * 3
    page = _make_page("policy", 1, eligibility + duration)

    chunker = SemanticChunker(embedder=HashingEmbedder(), min_chunk_tokens=5, max_chunk_tokens=1000)
    chunks = chunker.chunk_pages([page])

    assert len(chunks) >= 1
    assert all(c.chunking_strategy == "semantic" for c in chunks)
    assert all(c.document_id == "policy" for c in chunks)
    # chunk_index sequential starting at 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_semantic_chunker_handles_single_sentence_document():
    page = _make_page("short_doc", 1, "This policy has just one sentence.")
    chunker = SemanticChunker(embedder=HashingEmbedder())

    chunks = chunker.chunk_pages([page])

    assert len(chunks) == 1
    assert chunks[0].text == "This policy has just one sentence."


def test_semantic_chunker_empty_input_returns_no_chunks():
    chunker = SemanticChunker(embedder=HashingEmbedder())
    assert chunker.chunk_pages([]) == []


def test_semantic_chunker_enforces_min_chunk_tokens():
    # Many tiny one-clause "sentences" that would each be far below
    # min_chunk_tokens on their own — they should get merged forward.
    text = ". ".join(f"Point {i} is short" for i in range(10)) + "."
    page = _make_page("policy", 1, text)

    chunker = SemanticChunker(embedder=HashingEmbedder(), min_chunk_tokens=30, max_chunk_tokens=1000)
    chunks = chunker.chunk_pages([page])

    from app.utils.token_counter import count_tokens

    # Every chunk except possibly the last should meet the minimum.
    for chunk in chunks[:-1]:
        assert count_tokens(chunk.text) >= 30


def test_semantic_chunker_enforces_max_chunk_tokens():
    long_text = "This is a filler sentence about company policy details. " * 100
    page = _make_page("policy", 1, long_text)

    chunker = SemanticChunker(embedder=HashingEmbedder(), min_chunk_tokens=1, max_chunk_tokens=50)
    chunks = chunker.chunk_pages([page])

    from app.utils.token_counter import count_tokens

    assert len(chunks) > 1
    for chunk in chunks:
        assert count_tokens(chunk.text) <= 60  # small slack for sentence-boundary rounding


def test_semantic_chunker_multiple_documents_independent():
    page_a = _make_page("doc_a", 1, "Doc A sentence one. Doc A sentence two.")
    page_b = _make_page("doc_b", 1, "Doc B sentence one. Doc B sentence two.")

    chunker = SemanticChunker(embedder=HashingEmbedder(), min_chunk_tokens=1)
    chunks = chunker.chunk_pages([page_a, page_b])

    doc_ids = {c.document_id for c in chunks}
    assert doc_ids == {"doc_a", "doc_b"}


if __name__ == "__main__":
    test_split_sentences_basic()
    test_split_sentences_handles_empty_text()
    test_semantic_chunker_produces_chunks_from_multiple_sentences()
    test_semantic_chunker_handles_single_sentence_document()
    test_semantic_chunker_empty_input_returns_no_chunks()
    test_semantic_chunker_enforces_min_chunk_tokens()
    test_semantic_chunker_enforces_max_chunk_tokens()
    test_semantic_chunker_multiple_documents_independent()
    print("✅ All semantic chunking tests passed.")