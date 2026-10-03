import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import app.api.query as query_module
from app.core.dependencies import get_rag_pipeline
from app.main import app

from tests.test_api import _build_fake_pipeline  # noqa: E402


def test_compare_runs_each_strategy_and_isolates_missing_ones(tmp_path, monkeypatch):
    good = _build_fake_pipeline(tmp_path)

    def fake_load(chunking, retrieval):
        if chunking == "semantic":
            raise FileNotFoundError("No vector store for semantic")
        return good

    monkeypatch.setattr(query_module, "load_pipeline_for", fake_load)
    client = TestClient(app)
    response = client.post(
        "/query/compare",
        json={
            "question": "How much leave?",
            "strategies": [
                {"chunking_strategy": "fixed", "retrieval_strategy": "vector"},
                {"chunking_strategy": "semantic", "retrieval_strategy": "vector"},
            ],
        },
    )
    assert response.status_code == 200
    items = response.json()["results"]
    assert items[0]["result"]["answer"] and items[0]["error"] is None
    assert items[1]["result"] is None and "semantic" in items[1]["error"]


def test_compare_without_strategies_runs_all_eight(tmp_path, monkeypatch):
    good = _build_fake_pipeline(tmp_path)
    monkeypatch.setattr(query_module, "load_pipeline_for", lambda c, r: good)
    response = TestClient(app).post("/query/compare", json={"question": "q"})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 8


def test_top_k_override_does_not_mutate_the_shared_pipeline(tmp_path):
    pipeline = _build_fake_pipeline(tmp_path)
    original = pipeline.strategy.top_k
    app.dependency_overrides[get_rag_pipeline] = lambda: pipeline
    try:
        r = TestClient(app).post("/query", json={"question": "q", "top_k": 1})
        assert r.status_code == 200
        assert pipeline.strategy.top_k == original
    finally:
        app.dependency_overrides.clear()
