"""
Builds the prompt sent to the LLM: system instructions + a numbered
context block from retrieved chunks + the question. Numbering the
sources as [1], [2], ... and asking the model to cite them is what lets
answer_generator.py parse out which sources were actually used.
"""
from app.models.query import RetrievedChunk

SYSTEM_PROMPT = (
    "You are an assistant that answers questions using only the provided "
    "company document excerpts.\n"
    "- Answer using ONLY the information in the provided context. Do not use "
    "outside knowledge.\n"
    "- If the answer isn't in the context, say you don't know — do not make "
    "anything up.\n"
    "- Cite every factual claim with the bracketed source number it came "
    "from, e.g. [1]. Use multiple markers like [1][2] if a claim draws on "
    "more than one source.\n"
    "- Be concise and direct."
)


def build_context_block(retrieved: list[RetrievedChunk]) -> str:
    sections = []
    for i, item in enumerate(retrieved, start=1):
        chunk = item.chunk
        sections.append(
            f"[{i}] Source: {chunk.document_name} (department: {chunk.department}, "
            f"page: {chunk.page})\n{chunk.text}"
        )
    return "\n\n".join(sections)


def build_user_prompt(question: str, retrieved: list[RetrievedChunk]) -> str:
    if not retrieved:
        return (
            f"Question: {question}\n\n"
            "No relevant context was retrieved. Tell the user you couldn't "
            "find anything relevant in the knowledge base."
        )

    context = build_context_block(retrieved)
    return (
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer the question using only the context above. Cite sources "
        "inline like [1]."
    )
