"""
Runs every experiment configuration against the same evaluation dataset
and collects one EvaluationReport per experiment.
"""
from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.evaluation.dataset import EvalDataset
from app.evaluation.runner import EvaluationReport, EvaluationRunner
from app.pipelines.rag_pipeline import RAGPipeline
from app.pipelines.strategy import StrategyConfig

logger = get_logger(__name__)


@dataclass
class ExperimentRunResult:
    strategy: StrategyConfig
    report: EvaluationReport | None = None
    setup_error: str | None = None  # e.g. "no vector store for chunking=semantic"


@dataclass
class ExperimentBatch:
    results: list[ExperimentRunResult] = field(default_factory=list)

    def successful(self) -> list[ExperimentRunResult]:
        return [r for r in self.results if r.report is not None]

    def skipped(self) -> list[ExperimentRunResult]:
        return [r for r in self.results if r.setup_error is not None]

    def aggregates(self) -> dict[str, dict]:
        """{experiment_name: aggregate_dict} for every experiment that
        actually ran — exactly the shape app.experiments.comparison expects."""
        return {r.strategy.name: r.report.aggregate() for r in self.successful()}


class ExperimentBatchRunner:
    def __init__(self, settings: Settings | None = None, run_llm_judges: bool = True):
        self.settings = settings or get_settings()
        self.run_llm_judges = run_llm_judges

    def run(self, strategies: list[StrategyConfig], dataset: EvalDataset) -> ExperimentBatch:
        batch = ExperimentBatch()
        for strategy in strategies:
            batch.results.append(self._run_one(strategy, dataset))
        return batch

    def _run_one(self, strategy: StrategyConfig, dataset: EvalDataset) -> ExperimentRunResult:
        logger.info("Running experiment %s", strategy.name)
        try:
            pipeline = RAGPipeline(settings=self.settings, strategy=strategy)
        except FileNotFoundError as exc:
            logger.warning("Skipping experiment %s — %s", strategy.name, exc)
            return ExperimentRunResult(strategy=strategy, setup_error=str(exc))

        runner = EvaluationRunner(pipeline, run_llm_judges=self.run_llm_judges)
        report = runner.run(dataset)
        return ExperimentRunResult(strategy=strategy, report=report)