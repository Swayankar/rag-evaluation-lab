import json
import re

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_response(text: str) -> dict:
    """LLM judges sometimes wrap JSON in prose or markdown fences rather
    than returning a bare JSON object — pull out the first {...} block
    instead of requiring an exact json.loads on the whole response."""
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError(f"No JSON object found in judge response: {text!r}")
    return json.loads(match.group())


ANSWER_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator scoring a RAG system's answer against "
    "a reference answer. Score strictly on a 1-5 scale for each dimension:\n"
    "- correctness: does the answer state the same facts as the reference?\n"
    "- relevance: does the answer actually address the question asked?\n"
    "- completeness: does the answer cover everything the reference does?\n"
    "Respond with ONLY a JSON object, no other text: "
    '{"correctness": <1-5>, "relevance": <1-5>, "completeness": <1-5>, "rationale": "<one sentence>"}'
)


def build_answer_judge_prompt(question: str, reference_answer: str, actual_answer: str) -> str:
    return (
        f"Question: {question}\n\n"
        f"Reference answer: {reference_answer}\n\n"
        f"System's actual answer: {actual_answer}\n\n"
        "Score the system's answer as instructed."
    )


FAITHFULNESS_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator checking whether an answer is faithful "
    "to its provided source context — i.e. every factual claim in the "
    "answer is actually supported by the context, with no invented "
    "information (hallucination).\n"
    "Score faithfulness 1-5 (5 = fully supported by the context, 1 = "
    "mostly unsupported or invented). Respond with ONLY a JSON object, "
    "no other text: "
    '{"faithfulness": <1-5>, "likely_hallucination": <true|false>, "rationale": "<one sentence>"}'
)


def build_faithfulness_judge_prompt(context: str, answer: str) -> str:
    return (
        f"Source context:\n{context}\n\n"
        f"Answer to check:\n{answer}\n\n"
        "Score faithfulness as instructed."
    )
