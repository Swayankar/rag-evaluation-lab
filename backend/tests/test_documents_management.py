import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.jobs import JobAlreadyRunning, JobStore
from app.main import app

PDF = b"%PDF-1.4\n%fake but starts with the magic bytes\n"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        raw_docs_dir=str(tmp_path / "documents"),
        processed_chunks_dir=str(tmp_path / "chunks"),
        groq_api_key="super-secret-key",
        _env_file=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()


def _upload(client, dept="hr", name="leave_policy.pdf", data=PDF):
    return client.post("/documents/upload", data={"department": dept}, files=[("files", (name, data, "application/pdf"))])


def test_upload_then_library_lists_it_as_not_indexed(client):
    r = _upload(client)
    assert r.status_code == 201
    assert r.json()["saved"][0]["document_id"] == "leave_policy"

    lib = client.get("/documents/library").json()
    doc = lib["departments"][0]["documents"][0]
    assert doc["status"] == "not_indexed"
    assert lib["index"]["stale"] is True


def test_upload_rejects_non_pdf_and_fake_pdf(client):
    assert _upload(client, name="notes.txt").status_code == 400
    assert _upload(client, name="x.pdf", data=b"not a pdf").status_code == 400


def test_upload_rejects_duplicate_document_id_across_departments(client):
    assert _upload(client, dept="hr").status_code == 201
    r = _upload(client, dept="legal")
    assert r.status_code == 400
    assert "already exists" in str(r.json())


def test_upload_sanitizes_filename_and_blocks_traversal(client):
    r = _upload(client, name="../../evil name.pdf")
    assert r.status_code == 201
    assert r.json()["saved"][0]["filename"] == "evil_name.pdf"
    assert client.post("/documents/upload", data={"department": "../etc"}, files=[("files", ("a.pdf", PDF))]).status_code == 400


def test_delete_document_and_empty_folder(client):
    _upload(client)
    assert client.delete("/documents/hr/leave_policy.pdf").status_code == 200
    assert client.delete("/documents/hr/leave_policy.pdf").status_code == 404
    assert client.delete("/documents/folders/hr").status_code == 200


def test_delete_nonempty_folder_is_refused(client):
    _upload(client)
    assert client.delete("/documents/folders/hr").status_code == 409


def test_create_folder(client):
    assert client.post("/documents/folders", json={"name": "Finance Team"}).json() == {"name": "finance_team"}
    assert client.post("/documents/folders", json={"name": "finance_team"}).status_code == 409
    assert client.post("/documents/folders", json={"name": "library"}).status_code == 400


def test_config_never_leaks_the_api_key(client):
    r = client.get("/config")
    assert r.status_code == 200
    assert "super-secret-key" not in r.text
    assert r.json()["llm"]["api_key_configured"] is True


# --- job store (no HTTP) ---

def _wait(store, job_id, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        job = store.get(job_id)
        if job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(0.01)
    raise AssertionError("job didn't finish")


def test_job_runs_and_reports_progress():
    store = JobStore()

    def target(report):
        report(0.5, "halfway")
        return {"ok": True}

    job = _wait(store, store.start("t", target)["id"])
    assert job["status"] == "succeeded" and job["progress"] == 1.0 and job["result"] == {"ok": True}


def test_job_failure_is_captured_not_raised():
    store = JobStore()

    def boom(report):
        raise ValueError("nope")

    job = _wait(store, store.start("t", boom)["id"])
    assert job["status"] == "failed" and "nope" in job["error"]


def test_only_one_job_of_a_kind_at_a_time():
    store = JobStore()
    gate = {"go": False}

    def slow(report):
        while not gate["go"]:
            time.sleep(0.01)

    first = store.start("rebuild", slow)
    with pytest.raises(JobAlreadyRunning):
        store.start("rebuild", slow)
    gate["go"] = True
    _wait(store, first["id"])
    store.start("rebuild", lambda report: None)
