import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

ReportFn = Callable[[float, str], None]


class JobAlreadyRunning(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | succeeded | failed
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    error: str | None = None
    result: dict | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class JobStore:
    MAX_KEPT = 20

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()

    def start(self, kind: str, target: Callable[[ReportFn], dict | None]) -> dict:
        """Run `target(report)` in a background thread. `report(progress, message)`
        updates the job. Raises JobAlreadyRunning if one of this kind is active."""
        with self._lock:
            if self.is_running(kind):
                raise JobAlreadyRunning(f"A {kind} job is already running.")
            job = Job(id=uuid.uuid4().hex[:12], kind=kind)
            self._jobs[job.id] = job
            self._prune()
            snapshot = asdict(job)

        threading.Thread(target=self._run, args=(job, target), daemon=True, name=f"job-{job.id}").start()
        return snapshot

    def _run(self, job: Job, target: Callable[[ReportFn], dict | None]) -> None:
        def report(progress: float, message: str = "") -> None:
            with self._lock:
                job.progress = max(0.0, min(1.0, progress))
                job.message = message

        with self._lock:
            job.status = "running"
        try:
            result = target(report)
        except Exception as exc:  # noqa: BLE001 - a failed job is data, not a crash
            logger.exception("Job %s (%s) failed", job.id, job.kind)
            with self._lock:
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = time.time()
            return
        with self._lock:
            job.status = "succeeded"
            job.progress = 1.0
            job.result = result
            job.finished_at = time.time()

    def is_running(self, kind: str) -> bool:
        with self._lock:
            return any(j.kind == kind and j.status in ("queued", "running") for j in self._jobs.values())

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return asdict(job) if job else None

    def list(self, kind: str | None = None) -> list[dict]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if kind is None or j.kind == kind]
            return [asdict(j) for j in sorted(jobs, key=lambda j: j.created_at, reverse=True)]

    def _prune(self) -> None:
        finished = sorted(
            (j for j in self._jobs.values() if j.status in ("succeeded", "failed")),
            key=lambda j: j.created_at,
        )
        for job in finished[: max(0, len(self._jobs) - self.MAX_KEPT)]:
            self._jobs.pop(job.id, None)


job_store = JobStore()