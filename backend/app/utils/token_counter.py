"""
Centralized tokenizer access, shared by the fixed and semantic chunkers
so token counts are consistent between chunking strategies (important
when comparing them side by side).

Tries tiktoken (real token counts). If its encoding file can't be
downloaded (no network), falls back to whitespace-based counting — same
resilience pattern used elsewhere in this project (embeddings, the
reranker): degrade gracefully, never hard-crash ingestion over a
tokenizer download.
"""
from app.core.logging import get_logger

logger = get_logger(__name__)


class _WhitespaceEncoding:
    """Treats each whitespace-separated word as one "token". Real token
    counts will differ slightly from tiktoken's, but chunk boundaries
    still behave sensibly, and everything upgrades transparently to real
    tokens the moment tiktoken can reach the network."""

    def encode(self, text: str) -> list[str]:
        return text.split()

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


def _load_encoding():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception as exc:  # noqa: BLE001 - deliberately broad, this is a fallback
        logger.warning(
            "tiktoken encoding unavailable (%s) — falling back to whitespace "
            "tokenization. Token counts will be approximate.",
            exc,
        )
        return _WhitespaceEncoding()


_ENCODING = _load_encoding()


def encode(text: str) -> list:
    return _ENCODING.encode(text)


def decode(tokens: list) -> str:
    return _ENCODING.decode(tokens)


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))
