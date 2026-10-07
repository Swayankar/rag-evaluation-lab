import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.jobs import job_store
from app.experiments.recommend import recommend
from app.main import app


def _comparison(wins_by: dict[str, list[str]], values=None, directions=None):
    """Build a comparison payload where each experiment wins the listed metrics."""
    experiments = list(wins_by)
    directions = directions or {}
    metrics = []
    for name, won in wins_by.items():
        for m in won:
            vals = {e: (1.0 if e == name else 0.5) for e in experiments}
            if directions.get(m) == "lower":
                vals = {e: (0.1 if e == name else 0.9) for e in experiments}
            metrics.append({"metric": m, "direction": directions.get(m, "higher"), "values": vals, "best": name})
    return {"experiments": experiments, "metrics": metrics, "wins": {n: len(w) for n, w in wins_by.items()}}


# --------------------------------------------------------------------------
# recommend()
# --------------------------------------------------------------------------

def test_recommend_none_when_nothing_to_compare():
    assert recommend(None) is None
    assert recommend({"experiments": [], "metrics": []}) is None


def test_recommend_picks_most_wins_and_reports_clear_margin():
    rec = recommend(_comparison({
        "a": ["avg_mrr", "avg_recall_at_k", "avg_correctness", "avg_faithfulness"],
        "b": ["avg_latency_ms"],
    }))
    assert rec["name"] == "a" and rec["wins"] == 4 and rec["total_metrics"] == 5
    assert rec["confidence"] == "clear" and rec["margin"] == 3
    assert rec["runner_up"] == {"name": "b", "wins": 1}
    assert rec["weaknesses"] == ["avg_latency_ms"]


def test_recommend_tie_broken_by_quality_wins_not_speed():
    rec = recommend(_comparison({
        "fast": ["avg_latency_ms", "avg_prompt_tokens"],
        "accurate": ["avg_mrr", "avg_correctness"],
    }))
    assert rec["confidence"] == "tie"
    assert rec["name"] == "accurate"
    assert set(rec["tied"]) == {"fast", "accurate"}


def test_recommend_is_stable_on_a_complete_tie():
    first = recommend(_comparison({"b": ["avg_mrr"], "a": ["avg_recall_at_k"]}))
    second = recommend(_comparison({"a": ["avg_recall_at_k"], "b": ["avg_mrr"]}))
    assert first["name"] == second["name"] == "a"


def test_recommend_weakness_is_direction_aware():
    comparison = _comparison(
        {"a": ["avg_mrr", "avg_recall_at_k"], "b": ["hallucination_rate"]},
        directions={"hallucination_rate": "lower"},
    )
    rec = recommend(comparison)
    assert rec["name"] == "a"
    assert rec["weaknesses"] == ["hallucination_rate"]


def test_recommend_single_experiment():
    rec = recommend(_comparison({"only": ["avg_mrr"]}))
    assert rec["name"] == "only" and rec["confidence"] == "single" and rec["runner_up"] is None
    assert rec["weaknesses"] == []


def test_recommend_experiment_with_zero_wins_is_ranked_last():
    rec = recommend(_comparison({"a": ["avg_mrr"], "b": []}))
    assert [r["name"] for r in rec["ranking"]] == ["a", "b"]


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path):
    settings = Settings(
        raw_docs_dir=str(tmp_path / "documents"),
        eval_dataset_dir=str(tmp_path / "evaluation"),
        experiments_dir=str(tmp_path / "experiments"),
        _env_file=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app), settings
    app.dependency_overrides.clear()


def _write_comparison(settings, meta=None):
    directory = settings.experiments_results_dir
    directory.mkdir(parents=True)
    payload = _comparison({"a": ["avg_mrr", "avg_recall_at_k"], "b": ["avg_latency_ms"]})
    if meta:
        payload["meta"] = meta
    (directory / "comparison_latest.json").write_text(json.dumps(payload))


def _questions(client, text="How long?"):
    r = client.put("/evaluation/questions", json={"questions": [
        {"id": "q1", "question": text, "relevant_document_ids": ["policy"]}]})
    assert r.status_code == 200
    return r.json()["dataset_hash"]


def test_overview_without_a_comparison_is_empty_not_404(env):
    client, _ = env
    r = client.get("/experiments/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["comparison"] is None and body["recommendation"] is None and body["dataset_match"] is None
    assert client.get("/experiments").status_code == 404


def test_overview_recommends_and_flags_dataset_mismatch(env):
    client, settings = env
    current = _questions(client)
    _write_comparison(settings, meta={"dataset_hash": current})
    body = client.get("/experiments/overview").json()
    assert body["recommendation"]["name"] == "a"
    assert body["dataset_match"] is True

    _questions(client, text="A different question?")
    assert client.get("/experiments/overview").json()["dataset_match"] is False


def test_overview_dataset_match_unknown_for_cli_output(env):
    client, settings = env
    _questions(client)
    _write_comparison(settings)
    assert client.get("/experiments/overview").json()["dataset_match"] is None


def test_configs_default_to_the_canonical_five(env):
    client, _ = env
    body = client.get("/experiments/configs").json()
    assert body["from_files"] is False and len(body["experiments"]) == 5
    assert body["experiments"][-1]["retrieval_strategy"] == "hybrid_rerank"


def test_configs_roundtrip_writes_files_and_removes_stale_ones(env):
    client, settings = env
    five = client.get("/experiments/configs").json()["experiments"]
    assert client.put("/experiments/configs", json={"experiments": five}).json()["saved"] == 5
    assert len(list(Path(settings.experiments_dir).glob("experiment_*.json"))) == 5

    shorter = [{"name": "just_bm25", "chunking_strategy": "fixed", "retrieval_strategy": "bm25", "top_k": 8}]
    assert client.put("/experiments/configs", json={"experiments": shorter}).json()["files"] == ["experiment_001.json"]
    assert len(list(Path(settings.experiments_dir).glob("experiment_*.json"))) == 1

    got = client.get("/experiments/configs").json()
    assert got["from_files"] is True
    assert got["experiments"][0]["name"] == "just_bm25" and got["experiments"][0]["top_k"] == 8


def test_configs_validation(env):
    client, _ = env
    cfg = lambda name, **kw: {"name": name, "chunking_strategy": "fixed", "retrieval_strategy": "vector", **kw}

    dup = client.put("/experiments/configs", json={"experiments": [cfg("x"), cfg("x")]})
    assert dup.status_code == 422 and "duplicate" in dup.json()["detail"]

    for bad in ("has space", "../escape", "comparison_latest", "overview", "configs", "run"):
        r = client.put("/experiments/configs", json={"experiments": [cfg(bad)]})
        assert r.status_code == 422, bad

    assert client.put("/experiments/configs", json={"experiments": []}).status_code == 422
    assert client.put("/experiments/configs", json={"experiments": [cfg("ok", retrieval_strategy="nope")]}).status_code == 422
    assert client.put("/experiments/configs", json={"experiments": [cfg("ok", top_k=0)]}).status_code == 422


def test_configs_report_unreadable_files_instead_of_failing(env):
    client, settings = env
    directory = Path(settings.experiments_dir)
    directory.mkdir(parents=True)
    (directory / "experiment_001.json").write_text(json.dumps({"name": "ok", "retrieval_strategy": "bm25"}))
    (directory / "experiment_002.json").write_text("{not json")
    body = client.get("/experiments/configs").json()
    assert [c["name"] for c in body["experiments"]] == ["ok"]
    assert len(body["problems"]) == 1 and "experiment_002.json" in body["problems"][0]


def test_run_requires_questions(env):
    client, _ = env
    assert client.post("/experiments/run").status_code == 400


def test_run_is_blocked_while_another_job_runs(env):
    client, _ = env
    _questions(client)
    import threading
    release = threading.Event()
    job_store.start("evaluation", lambda report: release.wait(5) and None, owner="sample")
    try:
        r = client.post("/experiments/run")
        assert r.status_code == 409 and "evaluation" in r.json()["detail"]
        assert client.put("/experiments/configs", json={"experiments": [
            {"name": "x", "chunking_strategy": "fixed", "retrieval_strategy": "vector", "top_k": 5}]}).status_code == 200
    finally:
        release.set()


def test_detail_route_still_serves_experiment_files_and_rejects_traversal(env):
    client, settings = env
    settings.experiments_results_dir.mkdir(parents=True)
    (settings.experiments_results_dir / "experiment_1_fixed_vector.json").write_text(json.dumps({"aggregate": {}}))
    assert client.get("/experiments/experiment_1_fixed_vector").status_code == 200
    assert client.get("/experiments/nope").status_code == 404
    assert client.get("/experiments/..%2Fsecret").status_code in (400, 404)


# --------------------------------------------------------------------------
# run_experiments_job (pipeline + runner faked: this checks the job's own logic —
# files written, skipped experiments, progress, comparison payload)
# --------------------------------------------------------------------------

def test_run_job_writes_details_and_comparison_and_skips_missing_indexes(tmp_path, monkeypatch):
    import types

    from app.evaluation.dataset import EvalDataset, EvalQuestion
    from app.experiments import job as job_module
    from app.pipelines.strategy import StrategyConfig

    settings = Settings(experiments_dir=str(tmp_path / "experiments"), _env_file=None)
    dataset = EvalDataset(questions=[
        EvalQuestion(id="q1", question="a?", relevant_document_ids=["d"]),
        EvalQuestion(id="q2", question="b?", relevant_document_ids=["d"]),
    ])
    quality = {"good": 0.9, "meh": 0.4}

    class FakeEmbedder: ...

    def fake_pipeline(cfg, settings=None):
        if cfg.name == "no_index":
            raise FileNotFoundError("semantic index not built")
        return types.SimpleNamespace(strategy=cfg, embedder=FakeEmbedder(), retriever=types.SimpleNamespace())

    class FakeReport:
        def __init__(self, strategy_name):
            self.strategy_name, self.results = strategy_name, []

        def aggregate(self):
            q = quality[self.strategy_name]
            return {"avg_mrr": q, "avg_latency_ms": 100.0 if q > 0.5 else 50.0, "num_questions": len(self.results)}

    class FakeRunner:
        def __init__(self, pipeline, run_llm_judges=True):
            self.pipeline, self.run_llm_judges = pipeline, run_llm_judges

        def _evaluate_one(self, question):
            import dataclasses

            @dataclasses.dataclass
            class R:
                question_id: str
            return R(question.id)

    monkeypatch.setattr(job_module, "_pipeline_for", fake_pipeline)
    monkeypatch.setattr(job_module, "EvaluationReport", FakeReport)
    monkeypatch.setattr(job_module, "make_runner", lambda pipeline, settings, judges: FakeRunner(pipeline, run_llm_judges=judges))

    progress = []
    result = job_module.run_experiments_job(
        lambda p, m: progress.append((round(p, 2), m)),
        [StrategyConfig(name="good"), StrategyConfig(name="no_index"), StrategyConfig(name="meh")],
        dataset, settings, run_llm_judges=False,
    )

    assert result == {"ran": ["good", "meh"], "skipped": {"no_index": "semantic index not built"}}
    out = settings.experiments_results_dir
    detail = json.loads((out / "good.json").read_text())
    assert detail["aggregate"]["num_questions"] == 2 and len(detail["results"]) == 2
    assert detail["meta"]["embedder"] == "FakeEmbedder" and detail["meta"]["llm_judges"] is False

    comparison = json.loads((out / "comparison_latest.json").read_text())
    assert comparison["experiments"] == ["good", "meh"]
    assert comparison["skipped"] == {"no_index": "semantic index not built"}
    assert comparison["wins"] == {"good": 1, "meh": 1}
    assert comparison["meta"]["num_questions"] == 2 and comparison["meta"]["dataset_hash"]
    assert progress[-1] == (1.0, "Done.")
    assert all(a <= b for (a, _), (b, _) in zip(progress, progress[1:]))


def test_run_job_fails_clearly_when_nothing_can_run(tmp_path, monkeypatch):
    from app.evaluation.dataset import EvalDataset, EvalQuestion
    from app.experiments import job as job_module
    from app.pipelines.strategy import StrategyConfig

    def boom(cfg, settings=None):
        raise FileNotFoundError("no index")

    monkeypatch.setattr(job_module, "_pipeline_for", boom)
    settings = Settings(experiments_dir=str(tmp_path / "experiments"), _env_file=None)
    dataset = EvalDataset(questions=[EvalQuestion(id="q", question="?", relevant_document_ids=["d"])])
    with pytest.raises(RuntimeError, match="No experiment could run"):
        job_module.run_experiments_job(lambda p, m: None, [StrategyConfig(name="x")], dataset, settings, False)
    assert not (settings.experiments_results_dir / "comparison_latest.json").exists()
