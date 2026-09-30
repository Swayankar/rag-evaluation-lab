import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Settings
from app.embeddings.embedder import HashingEmbedder
from app.evaluation.dataset import EvalDataset, EvalQuestion
from app.experiments import registry
from app.experiments.comparison import compare, count_wins, format_markdown_table, save_comparison
from app.experiments.experiment_runner import ExperimentBatchRunner
from app.generation.answer_generator import AnswerGenerator
from app.models.document import Chunk
from app.pipelines.strategy import StrategyConfig
from app.retrieval.vector_search import VectorStore


class FakeLLM:
    def chat(self, system_prompt, user_prompt, **kwargs):
        return "Passwords need twelve characters [1]." if "password" in user_prompt.lower() else "Sixteen weeks [1]."


def _build_fixed_corpus(tmp_path: Path) -> Settings:
    """Sets up a Settings pointing at a real fixed-chunking vector store +
    chunks file, but deliberately leaves 'semantic' unbuilt — that gap is
    the point, see test_run_skips_experiments_with_unbuilt_prerequisites."""
    chunks = [
        Chunk(chunk_id="pw_000", document_id="password_policy", document_name="Password Policy",
              department="it", page=1, chunk_index=0, text="Passwords must be at least twelve characters."),
        Chunk(chunk_id="pl_000", document_id="parental_leave_policy", document_name="Parental Leave Policy",
              department="hr", page=1, chunk_index=0, text="Employees get sixteen weeks of leave."),
    ]
    embedder = HashingEmbedder()
    store = VectorStore()
    store.build(chunks, embedder.embed_texts([c.text for c in chunks]))

    processed_dir = tmp_path / "processed"
    (processed_dir / "chunks").mkdir(parents=True)
    (processed_dir / "chunks" / "fixed_chunks.json").write_text(json.dumps([c.model_dump() for c in chunks]))
    store.save(processed_dir / "vector_store")

    return Settings(
        embedding_backend="hashing",
        processed_chunks_dir=str(processed_dir / "chunks"),
        vector_store_dir=str(processed_dir / "vector_store"),
        groq_api_key="fake-key",
        _env_file=None,
    )


DATASET = EvalDataset(
    questions=[
        EvalQuestion(id="q1", question="How long must a password be?", relevant_document_ids=["password_policy"]),
        EvalQuestion(id="q2", question="How many weeks of leave?", relevant_document_ids=["parental_leave_policy"]),
    ]
)


# --- registry ------------------------------------------------------------

def test_canonical_experiments_cover_all_5_from_the_architecture_doc():
    combos = {(c.chunking_strategy, c.retrieval_strategy) for c in registry.CANONICAL_EXPERIMENTS}
    assert combos == {
        ("fixed", "vector"),
        ("semantic", "vector"),
        ("fixed", "hybrid"),
        ("semantic", "hybrid"),
        ("semantic", "hybrid_rerank"),
    }
    assert len(registry.CANONICAL_EXPERIMENTS) == 5


def test_write_and_reload_canonical_experiment_files_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "experiments"
        paths = registry.write_canonical_experiment_files(directory)

        assert len(paths) == 5
        assert all(p.exists() for p in paths)

        loaded = registry.load_experiment_configs(directory)
        assert [c.name for c in loaded] == [c.name for c in registry.CANONICAL_EXPERIMENTS]
        assert loaded[0].chunking_strategy == "fixed"
        assert loaded[0].retrieval_strategy == "vector"


def test_load_falls_back_to_canonical_when_directory_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        loaded = registry.load_experiment_configs(Path(tmp) / "does-not-exist")
        assert loaded == registry.CANONICAL_EXPERIMENTS


def test_custom_experiment_file_is_honored():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "experiments"
        directory.mkdir()
        (directory / "experiment_001.json").write_text(
            json.dumps({"name": "my_custom_experiment", "chunking_strategy": "fixed",
                       "retrieval_strategy": "bm25", "top_k": 10})
        )
        loaded = registry.load_experiment_configs(directory)
        assert len(loaded) == 1
        assert loaded[0].name == "my_custom_experiment"
        assert loaded[0].top_k == 10


# --- experiment_runner ----------------------------------------------------

def test_batch_runner_runs_multiple_strategies_against_one_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        settings = _build_fixed_corpus(Path(tmp))
        strategies = [
            StrategyConfig(name="fixed_vector", chunking_strategy="fixed", retrieval_strategy="vector"),
            StrategyConfig(name="fixed_bm25", chunking_strategy="fixed", retrieval_strategy="bm25"),
        ]
        runner = ExperimentBatchRunner(settings=settings, run_llm_judges=False)

        # Both experiments need a GroqClient-shaped generator; patch it in
        # by building pipelines through the same injection path the runner
        # itself doesn't expose — instead, verify via the public run() with
        # a monkeypatched AnswerGenerator default is out of scope here, so
        # this test focuses on what ExperimentBatchRunner controls: which
        # experiments ran vs were skipped, using no_llm_judges to avoid any
        # real Groq call requirement for *judging* (retrieval still needs
        # the pipeline to answer, so we still need a working LLM client).
        import app.pipelines.rag_pipeline as rag_pipeline_module

        original_answer_generator = rag_pipeline_module.AnswerGenerator
        rag_pipeline_module.AnswerGenerator = lambda: AnswerGenerator(llm_client=FakeLLM())
        try:
            batch = runner.run(strategies, DATASET)
        finally:
            rag_pipeline_module.AnswerGenerator = original_answer_generator

        assert len(batch.successful()) == 2
        assert batch.skipped() == []
        names = {r.strategy.name for r in batch.successful()}
        assert names == {"fixed_vector", "fixed_bm25"}


def test_run_skips_experiments_with_unbuilt_prerequisites_but_keeps_going():
    with tempfile.TemporaryDirectory() as tmp:
        settings = _build_fixed_corpus(Path(tmp))  # only "fixed" is built
        strategies = [
            StrategyConfig(name="fixed_vector", chunking_strategy="fixed", retrieval_strategy="vector"),
            StrategyConfig(name="semantic_vector", chunking_strategy="semantic", retrieval_strategy="vector"),
        ]
        runner = ExperimentBatchRunner(settings=settings, run_llm_judges=False)

        import app.pipelines.rag_pipeline as rag_pipeline_module

        original_answer_generator = rag_pipeline_module.AnswerGenerator
        rag_pipeline_module.AnswerGenerator = lambda: AnswerGenerator(llm_client=FakeLLM())
        try:
            batch = runner.run(strategies, DATASET)
        finally:
            rag_pipeline_module.AnswerGenerator = original_answer_generator

        assert [r.strategy.name for r in batch.successful()] == ["fixed_vector"]
        assert [r.strategy.name for r in batch.skipped()] == ["semantic_vector"]
        assert "semantic" in batch.skipped()[0].setup_error


def test_aggregates_only_include_successful_experiments():
    with tempfile.TemporaryDirectory() as tmp:
        settings = _build_fixed_corpus(Path(tmp))
        strategies = [
            StrategyConfig(name="fixed_vector", chunking_strategy="fixed", retrieval_strategy="vector"),
            StrategyConfig(name="semantic_vector", chunking_strategy="semantic", retrieval_strategy="vector"),
        ]
        runner = ExperimentBatchRunner(settings=settings, run_llm_judges=False)

        import app.pipelines.rag_pipeline as rag_pipeline_module

        original_answer_generator = rag_pipeline_module.AnswerGenerator
        rag_pipeline_module.AnswerGenerator = lambda: AnswerGenerator(llm_client=FakeLLM())
        try:
            batch = runner.run(strategies, DATASET)
        finally:
            rag_pipeline_module.AnswerGenerator = original_answer_generator

        aggregates = batch.aggregates()
        assert set(aggregates) == {"fixed_vector"}
        assert aggregates["fixed_vector"]["avg_recall_at_k"] == 1.0


# --- comparison ------------------------------------------------------------

AGGREGATES = {
    "fixed_vector": {
        "num_questions": 2, "avg_recall_at_k": 0.5, "avg_mrr": 0.5,
        "avg_latency_ms": 100.0, "hallucination_rate": 0.5,
    },
    "semantic_hybrid": {
        "num_questions": 2, "avg_recall_at_k": 1.0, "avg_mrr": 1.0,
        "avg_latency_ms": 300.0, "hallucination_rate": 0.0,
    },
}


def test_compare_picks_higher_is_better_correctly():
    rows = compare(AGGREGATES)
    recall_row = next(r for r in rows if r.metric == "avg_recall_at_k")
    assert recall_row.direction == "higher"
    assert recall_row.best_experiment == "semantic_hybrid"


def test_compare_picks_lower_is_better_correctly():
    rows = compare(AGGREGATES)
    latency_row = next(r for r in rows if r.metric == "avg_latency_ms")
    assert latency_row.direction == "lower"
    assert latency_row.best_experiment == "fixed_vector"  # 100ms < 300ms

    hallucination_row = next(r for r in rows if r.metric == "hallucination_rate")
    assert hallucination_row.best_experiment == "semantic_hybrid"  # 0.0 < 0.5


def test_compare_excludes_diagnostic_counts_from_the_table():
    rows = compare(AGGREGATES)
    assert "num_questions" not in {r.metric for r in rows}


def test_compare_handles_a_metric_missing_from_one_experiment():
    aggregates = {
        "a": {"avg_recall_at_k": 1.0, "avg_faithfulness": 5.0},
        "b": {"avg_recall_at_k": 0.5},  # no judge metrics — e.g. ran with --no-llm-judges
    }
    rows = compare(aggregates)
    faithfulness_row = next(r for r in rows if r.metric == "avg_faithfulness")
    assert faithfulness_row.values == {"a": 5.0}
    assert faithfulness_row.best_experiment == "a"


def test_count_wins_tallies_across_metrics():
    rows = compare(AGGREGATES)
    wins = count_wins(rows)
    assert wins["semantic_hybrid"] >= 2  # recall + mrr + hallucination
    assert wins["fixed_vector"] >= 1  # latency


def test_markdown_table_marks_the_winner():
    rows = compare(AGGREGATES)
    table = format_markdown_table(rows, ["fixed_vector", "semantic_hybrid"])
    assert "🏆" in table
    assert "avg_recall_at_k" in table
    lines = [line for line in table.splitlines() if line.startswith("| avg_recall_at_k")]
    assert "1.000 🏆" in lines[0]  # semantic_hybrid's value, marked


def test_markdown_table_shows_dash_for_missing_values():
    aggregates = {"a": {"avg_faithfulness": 5.0}, "b": {}}
    rows = compare(aggregates)
    table = format_markdown_table(rows, ["a", "b"])
    line = next(line for line in table.splitlines() if "avg_faithfulness" in line)
    assert "—" in line


def test_save_comparison_writes_expected_shape():
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "results" / "comparison_latest.json"
        rows = compare(AGGREGATES)
        save_comparison(rows, list(AGGREGATES), {"broken_experiment": "vector store missing"}, out_path)

        data = json.loads(out_path.read_text())
        assert data["experiments"] == list(AGGREGATES)
        assert data["skipped"] == {"broken_experiment": "vector store missing"}
        assert any(m["metric"] == "avg_recall_at_k" for m in data["metrics"])
        assert "wins" in data


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))