import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app

PDF = b"%PDF-1.4\nfake\n"


@pytest.fixture
def env(tmp_path):
    settings = Settings(
        raw_docs_dir=str(tmp_path / "documents"),
        processed_chunks_dir=str(tmp_path / "chunks"),
        vector_store_dir=str(tmp_path / "vector_store"),
        eval_dataset_dir=str(tmp_path / "evaluation"),
        experiments_dir=str(tmp_path / "experiments"),
        _env_file=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app), settings
    app.dependency_overrides.clear()


def _q(id="q1", docs=("password_policy",), text="How long?", **kw):
    return {"id": id, "question": text, "relevant_document_ids": list(docs), **kw}


def test_questions_roundtrip_and_hash_changes_on_edit(env):
    client, _ = env
    assert client.get("/evaluation/questions").json()["exists"] is False

    r = client.put("/evaluation/questions", json={"questions": [_q(expected_answer="  twelve  ", category="")]})
    assert r.status_code == 200
    first_hash = r.json()["dataset_hash"]

    got = client.get("/evaluation/questions").json()
    assert got["questions"][0]["expected_answer"] == "twelve"  # trimmed
    assert got["questions"][0]["category"] is None  # blank -> None

    r2 = client.put("/evaluation/questions", json={"questions": [_q(text="How many characters?")]})
    assert r2.json()["dataset_hash"] != first_hash


def test_put_rejects_duplicate_ids_empty_text_and_missing_docs(env):
    client, _ = env
    bad = {"questions": [_q("a"), _q("a"), _q("b", text="  "), _q("c", docs=[])]}
    r = client.put("/evaluation/questions", json=bad)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "duplicate id" in detail and "empty" in detail and "at least one relevant document" in detail


def test_put_warns_about_unknown_document_ids(env):
    client, _ = env
    r = client.put("/evaluation/questions", json={"questions": [_q(docs=["ghost_doc"])]})
    assert r.status_code == 200
    assert "ghost_doc" in r.json()["warnings"][0]


def test_run_requires_questions(env):
    client, _ = env
    r = client.post("/evaluation/run", json={"strategies": [{"chunking_strategy": "fixed", "retrieval_strategy": "vector"}]})
    assert r.status_code == 400


def test_results_listing_flags_dataset_mismatch(env):
    client, settings = env
    client.put("/evaluation/questions", json={"questions": [_q()]})
    current = client.get("/evaluation/questions").json()["dataset_hash"]

    results = settings.eval_results_dir
    results.mkdir(parents=True)
    (results / "fixed_vector.json").write_text(json.dumps({"aggregate": {"avg_mrr": 1.0}, "meta": {"dataset_hash": current}}))
    (results / "semantic_hybrid.json").write_text(json.dumps({"aggregate": {"avg_mrr": 0.5}, "meta": {"dataset_hash": "deadbeef"}}))
    (results / "fixed_bm25.json").write_text(json.dumps({"aggregate": {"avg_mrr": 0.2}}))  # CLI result, no meta

    items = {i["name"]: i for i in client.get("/evaluation/results").json()["results"]}
    assert items["fixed_vector"]["dataset_match"] is True
    assert items["semantic_hybrid"]["dataset_match"] is False
    assert items["fixed_bm25"]["dataset_match"] is None
    assert items["semantic_hybrid"]["retrieval"] == "hybrid"


def test_result_name_traversal_is_rejected(env):
    client, _ = env
    assert client.get("/evaluation/results/..%2Fsecret").status_code in (400, 404)


def test_reset_requires_confirmation_and_clears_everything(env):
    client, settings = env
    client.post("/documents/upload", data={"department": "hr"}, files=[("files", ("a_policy.pdf", PDF))])
    client.put("/evaluation/questions", json={"questions": [_q()]})
    settings.eval_results_dir.mkdir(parents=True)
    (settings.eval_results_dir / "fixed_vector.json").write_text("{}")

    assert client.post("/documents/reset", json={"confirm": "yes"}).status_code == 422

    r = client.post("/documents/reset", json={"confirm": "RESET", "clear_questions": True, "clear_results": True})
    assert r.status_code == 200
    assert r.json()["deleted_documents"] == 1
    assert sorted(r.json()["cleared"]) == ["questions", "results"]
    assert client.get("/documents/library").json()["total_documents"] == 0
    assert client.get("/evaluation/questions").json()["exists"] is False


def test_reset_keeps_questions_unless_asked(env):
    client, _ = env
    client.put("/evaluation/questions", json={"questions": [_q()]})
    client.post("/documents/reset", json={"confirm": "RESET"})
    assert client.get("/evaluation/questions").json()["exists"] is True


def test_reset_can_keep_folders(env):
    client, _ = env
    client.post("/documents/upload", data={"department": "hr"}, files=[("files", ("a_policy.pdf", PDF))])
    r = client.post("/documents/reset", json={"confirm": "RESET", "keep_folders": True})
    assert r.json()["deleted_documents"] == 1 and r.json()["deleted_folders"] == 0
    lib = client.get("/documents/library").json()
    assert [d["name"] for d in lib["departments"]] == ["hr"] and lib["total_documents"] == 0


def test_reset_can_clear_experiment_results_but_keeps_definitions(env):
    client, settings = env
    results = settings.experiments_results_dir
    results.mkdir(parents=True)
    (results / "comparison_latest.json").write_text("{}")
    definition = results.parent / "experiment_001.json"
    definition.write_text("{}")

    client.post("/documents/reset", json={"confirm": "RESET"})
    assert results.exists()

    r = client.post("/documents/reset", json={"confirm": "RESET", "clear_experiments": True})
    assert "experiments" in r.json()["cleared"]
    assert not results.exists() and definition.exists()
