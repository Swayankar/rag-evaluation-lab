"""
Evaluation dataset: a small, hand-authored set of realistic questions
with expected answers/keywords and which documents should be considered
relevant sources.

Ground truth is deliberately DOCUMENT-level, not chunk-level: authoring
"chunk_042 is the right chunk" by hand is brittle (chunk boundaries move
every time you change chunk_size or switch to semantic chunking) and
impractical to write by hand for 20 real documents. "This question
should be answered from parental_leave_policy" is realistic to author
once and stays valid across every chunking/retrieval strategy you test.
"""
import json
from pathlib import Path

from pydantic import BaseModel, Field


class EvalQuestion(BaseModel):
    id: str
    question: str
    relevant_document_ids: list[str] = Field(
        description="document_id values (matching Chunk.document_id — the PDF filename without extension) that should be retrieved for this question"
    )
    expected_answer: str | None = Field(
        default=None,
        description="A reference answer. If set, the LLM judge scores correctness/relevance/completeness against it.",
    )
    expected_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords/phrases the answer should probably contain — not currently scored automatically, but useful context when reading results by eye.",
    )
    category: str | None = None


class EvalDataset(BaseModel):
    questions: list[EvalQuestion]

    def __len__(self) -> int:
        return len(self.questions)


def load_eval_dataset(path: Path) -> EvalDataset:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return EvalDataset(questions=[EvalQuestion(**q) for q in data["questions"]])

STARTER_TEMPLATE = {
    "questions": [
        {
            "id": "q1",
            "question": "How many weeks of paid parental leave are employees entitled to?",
            "relevant_document_ids": ["parental_leave_policy"],
            "expected_answer": "Sixteen weeks of paid parental leave.",
            "expected_keywords": ["sixteen", "weeks"],
            "category": "HR",
        },
        {
            "id": "q2",
            "question": "What is the minimum password length required by the security policy?",
            "relevant_document_ids": ["password_policy"],
            "expected_answer": "Passwords must be at least twelve characters long.",
            "expected_keywords": ["twelve", "characters"],
            "category": "IT",
        },
        {
            "id": "q3",
            "question": "Above what dollar amount does an expense require an itemized receipt?",
            "relevant_document_ids": ["expense_policy"],
            "expected_answer": "Expenses over twenty five dollars require an itemized receipt.",
            "expected_keywords": ["twenty five", "receipt"],
            "category": "Finance",
        },
    ]
}


def write_starter_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(STARTER_TEMPLATE, f, indent=2)
