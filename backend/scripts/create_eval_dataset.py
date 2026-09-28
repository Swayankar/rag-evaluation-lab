#!/usr/bin/env python
"""
Helper: scaffold data/evaluation/questions.json.

Usage:
    cd backend
    python scripts/create_eval_dataset.py

If the file doesn't exist yet, this writes a small starter template
with 3 example questions matching the sample HR/IT/Finance corpus. 
Edit it to match the real documents:
  - relevant_document_ids must match the `document_id` field in your
    chunks — i.e. the PDF filename without its extension
    (parental_leave_policy.pdf -> "parental_leave_policy")
  - expected_answer is what the LLM judge scores correctness against
  - expected_keywords is just for your own reading of results; nothing
    scores against it automatically yet

If the file already exists, this validates it loads correctly and
reports how many questions it has, without overwriting anything.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.evaluation.dataset import load_eval_dataset, write_starter_template  # noqa: E402


def main() -> None:
    settings = get_settings()
    path = settings.eval_dataset_path

    if path.exists():
        dataset = load_eval_dataset(path)
        print(f"{path} already exists with {len(dataset)} question(s) — leaving it as is.")
        for q in dataset.questions:
            print(f"  {q.id}: {q.question!r} -> {q.relevant_document_ids}")
        return

    write_starter_template(path)
    print(f"Wrote a starter template to {path}.")
    print(
        f"\nEdit {path} to match your real documents before running "
        "scripts/run_experiment.py — in particular, relevant_document_ids "
        "must match real document_id values from your ingested chunks "
        "(the PDF filename without .pdf, e.g. 'remote_work_policy.pdf' -> "
        "'remote_work_policy')."
    )


if __name__ == "__main__":
    main()
