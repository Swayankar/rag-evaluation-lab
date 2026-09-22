import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from app.embeddings.embedder import HashingEmbedder
from app.models.document import Chunk
from app.retrieval.vector_search import VectorStore


def _make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc",
        document_name="Doc",
        department="hr",
        page=1,
        chunk_index=0,
        text=text,
    )


def test_vector_store_search_returns_nearest_first():
    chunks = [_make_chunk(f"c{i}", f"chunk {i}") for i in range(4)]
    # 4 orthonormal-ish vectors so nearest-neighbour order is unambiguous
    embeddings = np.eye(4, dtype=np.float32)

    store = VectorStore()
    store.build(chunks, embeddings)

    query = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    results = store.search(query, top_k=2)

    assert results[0][0].chunk_id == "c0"
    assert results[0][1] > results[1][1]


def test_vector_store_save_and_load_roundtrip():
    chunks = [_make_chunk(f"c{i}", f"chunk {i}") for i in range(3)]
    embeddings = np.random.default_rng(0).random((3, 8)).astype(np.float32)

    store = VectorStore()
    store.build(chunks, embeddings)

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "vector_store"
        store.save(directory)
        loaded = VectorStore.load(directory)

    assert len(loaded) == 3
    assert loaded._chunks[0].chunk_id == "c0"
    np.testing.assert_allclose(loaded._embeddings, store._embeddings)


def test_hashing_embedder_is_deterministic_and_normalized():
    embedder = HashingEmbedder(dimension=64)
    vectors = embedder.embed_texts(["hello world", "hello world"])

    np.testing.assert_allclose(vectors[0], vectors[1])
    np.testing.assert_allclose(np.linalg.norm(vectors[0]), 1.0, atol=1e-5)


if __name__ == "__main__":
    test_vector_store_search_returns_nearest_first()
    test_vector_store_save_and_load_roundtrip()
    test_hashing_embedder_is_deterministic_and_normalized()
    print("✅ All retrieval tests passed.")
