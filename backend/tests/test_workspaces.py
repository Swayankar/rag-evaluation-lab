import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core import dependencies as deps
from app.core import workspaces as ws_module
from app.core.config import Settings, get_settings
from app.core.jobs import job_store
from app.ingestion.index_builder import rebuild_index
from app.main import app

PDF = b"%PDF-1.4\n%fake but starts with the magic bytes\n"
KEY_A = "gsk_visitorAAAAAAAAAAAA"
KEY_B = "gsk_visitorBBBBBBBBBBBB"


def make_settings(tmp_path, **overrides):
    sample = tmp_path / "sample"
    values = dict(
        app_mode="hosted",
        raw_docs_dir=str(sample / "documents"),
        processed_chunks_dir=str(sample / "chunks"),
        vector_store_dir=str(sample / "vector_store"),
        eval_dataset_dir=str(sample / "evaluation"),
        experiments_dir=str(sample / "experiments"),
        workspaces_dir=str(tmp_path / "workspaces"),
        groq_api_key="SERVER-SECRET-KEY",
        embedding_backend="hashing",
        max_workspaces_per_ip_per_hour=0,
        _env_file=None,
    )
    values.update(overrides)
    return Settings(**values)


def seed_sample(settings):
    """A sample with one document, a built index and one question — written directly,
    the way the owner's committed data would already exist."""
    folder = settings.raw_docs_path / "hr"
    folder.mkdir(parents=True)
    (folder / "handbook.pdf").write_bytes(PDF)
    rebuild_index(lambda p, m: None, None, settings)
    settings.eval_dataset_path.parent.mkdir(parents=True, exist_ok=True)
    settings.eval_dataset_path.write_text(
        '{"questions": [{"id": "q1", "question": "How much leave?", "relevant_document_ids": ["handbook"]}]}'
    )


@pytest.fixture(autouse=True)
def clean_state():
    deps.clear_pipeline_cache()
    ws_module._create_log.clear()
    ws_module._last_touched.clear()
    yield
    app.dependency_overrides.clear()
    deps.clear_pipeline_cache()


@pytest.fixture
def hosted(tmp_path):
    settings = make_settings(tmp_path)
    seed_sample(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), settings


def new_workspace(client, copy_sample=False) -> str:
    r = client.post("/workspaces", json={"copy_sample": copy_sample})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def H(ws=None, key=None):
    headers = {}
    if ws:
        headers["X-Workspace"] = ws
    if key:
        headers["X-Groq-Key"] = key
    return headers


def upload(client, ws, name="policy.pdf", dept="legal"):
    return client.post("/documents/upload", data={"department": dept},
                       files=[("files", (name, PDF, "application/pdf"))], headers=H(ws))


def doc_ids(client, ws=None):
    lib = client.get("/documents/library", headers=H(ws)).json()
    return sorted(d["document_id"] for dept in lib["departments"] for d in dept["documents"])


def wait_for(client, job_id, ws, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        job = client.get(f"/jobs/{job_id}", headers=H(ws)).json()
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


# --------------------------------------------------------------------------
# the sample is read-only in hosted mode
# --------------------------------------------------------------------------

def test_sample_is_readable_by_everyone(hosted):
    client, _ = hosted
    assert doc_ids(client) == ["handbook"]
    assert client.get("/evaluation/questions").json()["questions"][0]["id"] == "q1"
    me = client.get("/workspaces/current").json()
    assert me["is_sample"] and me["read_only"] and me["limits"] is None


@pytest.mark.parametrize("method,path,kwargs", [
    ("post", "/documents/upload", dict(data={"department": "x"}, files=[("files", ("a.pdf", PDF, "application/pdf"))])),
    ("post", "/documents/folders", dict(json={"name": "newdept"})),
    ("delete", "/documents/hr/handbook.pdf", {}),
    ("post", "/documents/rebuild", {}),
    ("post", "/documents/reset", dict(json={"confirm": "RESET", "clear_questions": True})),
    ("put", "/evaluation/questions", dict(json={"questions": []})),
    ("post", "/evaluation/run", dict(json={"strategies": [{"chunking_strategy": "fixed", "retrieval_strategy": "vector"}]})),
    ("delete", "/evaluation/results/fixed_vector", {}),
    ("put", "/experiments/configs", dict(json={"experiments": []})),
    ("post", "/experiments/run", {}),
])
def test_every_write_to_the_sample_is_refused_and_changes_nothing(hosted, method, path, kwargs):
    client, settings = hosted
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 403, (path, r.status_code, r.text)
    assert "read-only" in r.json()["detail"]
    assert doc_ids(client) == ["handbook"]
    assert settings.eval_dataset_path.exists() and settings.chunks_path_for("fixed").exists()


def test_explicit_sample_header_is_still_read_only(hosted):
    client, _ = hosted
    r = client.post("/documents/folders", json={"name": "x"}, headers=H("sample"))
    assert r.status_code == 403


def test_local_mode_leaves_the_sample_editable(tmp_path):
    settings = make_settings(tmp_path, app_mode="local")
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    assert upload(client, None, name="mine.pdf").status_code == 201
    assert "mine" in doc_ids(client)


# --------------------------------------------------------------------------
# private workspaces are isolated from the sample and from each other
# --------------------------------------------------------------------------

def test_private_workspace_starts_empty_and_never_touches_the_sample(hosted):
    client, settings = hosted
    a = new_workspace(client)
    assert doc_ids(client, a) == []
    assert upload(client, a, "policy.pdf").status_code == 201
    assert doc_ids(client, a) == ["policy"]
    assert doc_ids(client) == ["handbook"]  # sample unchanged
    assert not (settings.raw_docs_path / "legal").exists()


def test_two_workspaces_cannot_see_each_other(hosted):
    client, _ = hosted
    a, b = new_workspace(client), new_workspace(client)
    upload(client, a, "alpha.pdf", "d")
    upload(client, b, "beta.pdf", "d")
    assert doc_ids(client, a) == ["alpha"]
    assert doc_ids(client, b) == ["beta"]
    assert upload(client, a, "same.pdf").status_code == 201
    assert upload(client, b, "same.pdf").status_code == 201


def test_questions_results_and_experiments_are_per_workspace(hosted):
    client, _ = hosted
    a, b = new_workspace(client), new_workspace(client)
    upload(client, a, "alpha.pdf", "d")
    q = {"questions": [{"id": "x", "question": "?", "relevant_document_ids": ["alpha"]}]}
    assert client.put("/evaluation/questions", json=q, headers=H(a)).status_code == 200
    assert client.get("/evaluation/questions", headers=H(a)).json()["exists"] is True
    assert client.get("/evaluation/questions", headers=H(b)).json()["exists"] is False
    assert client.get("/evaluation/questions").json()["questions"][0]["id"] == "q1"  # sample's own

    cfg = {"experiments": [{"name": "mine", "chunking_strategy": "fixed", "retrieval_strategy": "bm25", "top_k": 3}]}
    assert client.put("/experiments/configs", json=cfg, headers=H(a)).status_code == 200
    assert client.get("/experiments/configs", headers=H(a)).json()["experiments"][0]["name"] == "mine"
    assert client.get("/experiments/configs", headers=H(b)).json()["from_files"] is False


def test_reset_in_a_private_workspace_does_not_touch_the_sample_or_others(hosted):
    client, settings = hosted
    a = new_workspace(client, copy_sample=True)
    b = new_workspace(client, copy_sample=True)
    r = client.post("/documents/reset", json={"confirm": "RESET", "clear_questions": True}, headers=H(a))
    assert r.status_code == 200, r.text
    assert doc_ids(client, a) == []
    assert doc_ids(client, b) == ["handbook"]
    assert doc_ids(client) == ["handbook"]
    assert settings.eval_dataset_path.exists() and settings.chunks_path_for("fixed").exists()


def test_copy_sample_gives_documents_index_and_questions_but_not_results(hosted):
    client, settings = hosted
    (settings.eval_results_dir).mkdir(parents=True)
    (settings.eval_results_dir / "fixed_vector.json").write_text('{"aggregate": {}}')
    a = new_workspace(client, copy_sample=True)
    assert doc_ids(client, a) == ["handbook"]
    lib = client.get("/documents/library", headers=H(a)).json()
    assert lib["index"]["fixed_built"] and lib["documents" if False else "index"]["total_chunks"] == 1
    assert client.get("/evaluation/questions", headers=H(a)).json()["questions"][0]["id"] == "q1"
    assert client.get("/evaluation/results", headers=H(a)).json()["results"] == []
    client.delete("/documents/hr/handbook.pdf", headers=H(a))
    assert doc_ids(client) == ["handbook"]


def test_unknown_or_malformed_workspace_ids_are_rejected(hosted):
    client, _ = hosted
    assert client.get("/documents/library", headers=H("0" * 20)).status_code == 410
    assert client.get("/documents/library", headers=H("../../etc")).status_code == 400
    assert client.get("/documents/library", headers=H("sample/../x")).status_code == 400


def test_deleting_a_workspace_removes_it_and_only_it(hosted):
    client, settings = hosted
    a, b = new_workspace(client), new_workspace(client)
    assert client.delete(f"/workspaces/{b}", headers=H(a)).status_code == 403  # not yours
    assert client.delete(f"/workspaces/{a}").status_code == 403  # no header = sample
    assert client.delete("/workspaces/sample", headers=H(a)).status_code == 403
    assert client.delete(f"/workspaces/{a}", headers=H(a)).status_code == 200
    assert client.get("/documents/library", headers=H(a)).status_code == 410
    assert client.get("/documents/library", headers=H(b)).status_code == 200
    assert doc_ids(client) == ["handbook"]


# --------------------------------------------------------------------------
# Groq keys
# --------------------------------------------------------------------------

def test_hosted_sample_never_spends_the_server_key(hosted):
    client, _ = hosted
    r = client.post("/query", json={"question": "q"})
    assert r.status_code == 400 and "Groq API key" in r.json()["detail"]
    assert client.post("/evaluation/run", json={"strategies": [
        {"chunking_strategy": "fixed", "retrieval_strategy": "vector"}]}, headers=H(new_workspace(client))
    ).status_code == 400
    me = client.get("/workspaces/current").json()
    assert me["key"] == {"server_key_allowed": False, "using_your_key": False, "can_use_llm": False}


def test_visitor_key_is_used_for_their_request_only(hosted):
    client, _ = hosted
    a = client.post("/query", json={"question": "q"}, headers=H(None, KEY_A))
    b = client.post("/query", json={"question": "q"}, headers=H(None, KEY_B))
    assert a.status_code == b.status_code == 200
    assert a.json()["answer"].endswith(KEY_A) and b.json()["answer"].endswith(KEY_B)
    for _, pipeline in deps.loaded_pipelines():
        assert pipeline._answer_generator is None
        assert pipeline.settings.groq_api_key == ""
    assert client.post("/query", json={"question": "q"}).status_code == 400


def test_compare_uses_the_callers_key_and_reports_missing_key_per_strategy(hosted):
    client, _ = hosted
    body = {"question": "q", "strategies": [{"chunking_strategy": "fixed", "retrieval_strategy": "vector"}]}
    ok = client.post("/query/compare", json=body, headers=H(None, KEY_A)).json()
    assert ok["results"][0]["result"]["answer"].endswith(KEY_A)
    none = client.post("/query/compare", json=body).json()
    assert none["results"][0]["result"] is None and "Groq API key" in none["results"][0]["error"]


def test_a_malformed_key_header_is_rejected_without_echoing_it(hosted):
    client, _ = hosted
    r = client.get("/config", headers={"X-Groq-Key": "bad key with spaces!"})
    assert r.status_code == 400 and "bad key" not in r.text


def test_config_never_exposes_any_key(hosted):
    client, _ = hosted
    for headers in (H(), H(None, KEY_A)):
        text = client.get("/config", headers=headers).text
        assert "SERVER-SECRET-KEY" not in text and KEY_A not in text
    cfg = client.get("/config", headers=H(None, KEY_A)).json()
    assert cfg["llm"]["key_source"] == "yours" and cfg["workspace"]["read_only"] is True
    assert client.get("/config").json()["llm"]["key_source"] == "none"


def test_evaluation_judges_use_the_visitors_key_and_results_stay_in_their_workspace(hosted):
    client, settings = hosted
    a = new_workspace(client, copy_sample=True)
    r = client.post("/evaluation/run", json={"strategies": [
        {"chunking_strategy": "fixed", "retrieval_strategy": "vector"}]}, headers=H(a, KEY_A))
    assert r.status_code == 202, r.text
    job = wait_for(client, r.json()["id"], a)
    assert job["status"] == "succeeded", job
    saved = client.get("/evaluation/results/fixed_vector", headers=H(a)).json()
    assert saved["results"][0]["answer"].endswith(KEY_A)
    assert saved["results"][0]["judge_key"] == KEY_A
    assert client.get("/evaluation/results", headers=H()).json()["results"] == []
    assert not settings.eval_results_dir.exists()


# --------------------------------------------------------------------------
# jobs
# --------------------------------------------------------------------------

def test_jobs_are_private_to_their_workspace(hosted):
    client, _ = hosted
    a, b = new_workspace(client), new_workspace(client)
    upload(client, a, "alpha.pdf", "d")
    job = client.post("/documents/rebuild", headers=H(a)).json()
    wait_for(client, job["id"], a)
    assert client.get(f"/jobs/{job['id']}", headers=H(b)).status_code == 404
    assert client.get(f"/jobs/{job['id']}").status_code == 404
    assert [j["id"] for j in client.get("/jobs", headers=H(a)).json()["jobs"]] == [job["id"]]
    assert client.get("/jobs", headers=H(b)).json()["jobs"] == []


def test_two_workspaces_can_run_jobs_at_once_but_the_server_wide_cap_holds(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, max_concurrent_jobs=2)
    seed_sample(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    release = threading.Event()
    import app.ingestion.index_builder as ib
    monkeypatch.setattr(ib, "rebuild_index", lambda report, chunking, s: release.wait(5) and {})

    a, b, c = (new_workspace(client, copy_sample=True) for _ in range(3))
    try:
        assert client.post("/documents/rebuild", headers=H(a)).status_code == 202
        assert client.post("/documents/rebuild", headers=H(a)).status_code == 409
        assert client.post("/documents/rebuild", headers=H(b)).status_code == 202
        r = client.post("/documents/rebuild", headers=H(c))
        assert r.status_code == 429 and "busy" in r.json()["detail"]
        assert client.delete(f"/workspaces/{a}", headers=H(a)).status_code == 409
    finally:
        release.set()


# --------------------------------------------------------------------------
# limits, creation caps, expiry
# --------------------------------------------------------------------------

def test_upload_limits_apply_to_private_workspaces(tmp_path):
    settings = make_settings(tmp_path, max_docs_per_workspace=2, max_upload_mb=1)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    a = new_workspace(client)
    assert upload(client, a, "one.pdf").status_code == 201
    assert upload(client, a, "two.pdf").status_code == 201
    r = upload(client, a, "three.pdf")
    assert r.status_code == 400 and "at most 2 documents" in str(r.json())
    big = client.post("/documents/upload", data={"department": "x"}, headers=H(a),
                      files=[("files", ("big.pdf", PDF + b"0" * (2 * 1024 * 1024), "application/pdf"))])
    assert big.status_code == 400
    assert client.get("/workspaces/current", headers=H(a)).json()["usage"]["documents"] == 2


def test_question_limit_applies_to_private_workspaces(tmp_path):
    settings = make_settings(tmp_path, max_questions_per_workspace=2)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    a = new_workspace(client)
    upload(client, a, "d.pdf", "x")
    qs = {"questions": [{"id": f"q{i}", "question": "?", "relevant_document_ids": ["d"]} for i in range(3)]}
    assert client.put("/evaluation/questions", json=qs, headers=H(a)).status_code == 422


def test_total_workspace_cap_and_per_ip_creation_limit(tmp_path):
    settings = make_settings(tmp_path, max_workspaces=2)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    new_workspace(client), new_workspace(client)
    r = client.post("/workspaces", json={})
    assert r.status_code == 503 and "limit" in r.json()["detail"]

    settings2 = make_settings(tmp_path / "again", max_workspaces_per_ip_per_hour=2)
    app.dependency_overrides[get_settings] = lambda: settings2
    new_workspace(client), new_workspace(client)
    assert client.post("/workspaces", json={}).status_code == 429


def test_idle_workspaces_expire_but_active_and_busy_ones_do_not(hosted):
    client, settings = hosted
    old, fresh, busy = new_workspace(client), new_workspace(client), new_workspace(client)
    long_ago = time.time() - 8 * 86400
    for ws_id in (old, busy):
        marker = Path(settings.workspaces_dir) / ws_id / ".last_used"
        os.utime(marker, (long_ago, long_ago))
    release = threading.Event()
    job_store.start("rebuild", lambda report: release.wait(5) and None, owner=busy)
    try:
        assert ws_module.reap_expired(settings) == [old]
    finally:
        release.set()
    assert client.get("/documents/library", headers=H(old)).status_code == 410
    assert client.get("/documents/library", headers=H(fresh)).status_code == 200
    assert client.get("/documents/library", headers=H(busy)).status_code == 200


def test_using_a_workspace_keeps_it_alive(hosted):
    client, settings = hosted
    a = new_workspace(client)
    marker = Path(settings.workspaces_dir) / a / ".last_used"
    os.utime(marker, (time.time() - 6 * 86400,) * 2)
    ws_module._last_touched.clear()
    client.get("/documents/library", headers=H(a))
    assert time.time() - marker.stat().st_mtime < 60
    assert ws_module.reap_expired(settings) == []


# --------------------------------------------------------------------------
# pipeline cache
# --------------------------------------------------------------------------

def test_pipeline_cache_is_per_workspace_bounded_and_clearable(tmp_path):
    settings = make_settings(tmp_path, pipeline_cache_size=2)
    seed_sample(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    a = new_workspace(client, copy_sample=True)

    s_sample = ws_module.workspace_settings.__wrapped__ if hasattr(ws_module.workspace_settings, "__wrapped__") else None
    assert s_sample is None
    client.post("/query", json={"question": "q"}, headers=H(None, KEY_A))
    client.post("/query", json={"question": "q"}, headers=H(a, KEY_A))
    keys = [(c, r) for (c, r), _ in deps.loaded_pipelines()]
    assert len(deps.loaded_pipelines("sample")) == 1 and len(deps.loaded_pipelines(a)) == 1 and len(keys) == 2

    client.post("/query", json={"question": "q", "retrieval_strategy": "bm25"}, headers=H(a, KEY_A))
    assert len(deps.loaded_pipelines()) == 2

    deps.clear_pipeline_cache(a)
    assert deps.loaded_pipelines(a) == [] and len(deps.loaded_pipelines()) <= 2


def test_rebuilding_one_workspace_does_not_flush_anothers_pipelines(hosted):
    client, _ = hosted
    a = new_workspace(client, copy_sample=True)
    client.post("/query", json={"question": "q"}, headers=H(None, KEY_A))
    assert len(deps.loaded_pipelines("sample")) == 1
    job = client.post("/documents/rebuild", headers=H(a)).json()
    wait_for(client, job["id"], a)
    assert len(deps.loaded_pipelines("sample")) == 1


# --------------------------------------------------------------------------
# model choice
# --------------------------------------------------------------------------

def test_model_defaults_and_lists_the_options(hosted):
    client, settings = hosted
    llm = client.get("/config").json()["llm"]
    assert llm["model"] == "openai/gpt-oss-20b" and llm["default_model"] == "openai/gpt-oss-20b"
    assert llm["options"][0] == "openai/gpt-oss-20b" and len(llm["options"]) == 3
    assert llm["model_overridden"] is False and llm["custom_allowed"] is False  # hosted, no own key


def test_listed_model_is_used_by_the_request_and_recorded(hosted):
    client, _ = hosted
    h = {**H(None, KEY_A), "X-Groq-Model": "openai/gpt-oss-120b"}
    assert client.get("/config", headers=h).json()["llm"]["model"] == "openai/gpt-oss-120b"
    seen = {}
    from app.generation import llm as llm_module
    original = llm_module.GroqClient.chat
    llm_module.GroqClient.chat = lambda self, s, u, **kw: seen.setdefault("model", self.settings.groq_model) or "ok"
    try:
        assert client.post("/query", json={"question": "q"}, headers=h).status_code == 200
    finally:
        llm_module.GroqClient.chat = original
    assert seen["model"] == "openai/gpt-oss-120b"


def test_custom_model_needs_the_visitors_own_key_when_hosted(hosted):
    client, _ = hosted
    custom = {"X-Groq-Model": "qwen/qwen3-32b"}
    assert client.get("/config", headers=custom).status_code == 400
    ok = client.get("/config", headers={**custom, **H(None, KEY_A)})
    assert ok.status_code == 200 and ok.json()["llm"]["model"] == "qwen/qwen3-32b"
    assert ok.json()["llm"]["custom_allowed"] is True


def test_malformed_model_names_are_rejected(hosted):
    client, _ = hosted
    for bad in ("bad model", "x;rm -rf", "../etc", "a" * 200):
        assert client.get("/config", headers={**H(None, KEY_A), "X-Groq-Model": bad}).status_code == 400


def test_custom_model_can_be_switched_off(tmp_path):
    settings = make_settings(tmp_path, allow_custom_model=False)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    r = client.get("/config", headers={**H(None, KEY_A), "X-Groq-Model": "qwen/qwen3-32b"})
    assert r.status_code == 400
    assert client.get("/config", headers={**H(None, KEY_A), "X-Groq-Model": "openai/gpt-oss-120b"}).status_code == 200


def test_local_mode_allows_any_model_and_binds_it_even_with_the_server_key(tmp_path):
    settings = make_settings(tmp_path, app_mode="local")
    seed_sample(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    seen = []
    from app.generation import llm as llm_module
    original = llm_module.GroqClient.chat
    llm_module.GroqClient.chat = lambda self, s, u, **kw: seen.append(self.settings.groq_model) or "ok"
    try:
        r = client.post("/query", json={"question": "q"}, headers={"X-Groq-Model": "some/custom-model"})
        assert r.status_code == 200, r.text
    finally:
        llm_module.GroqClient.chat = original
    assert seen == ["some/custom-model"]
