import requests

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.tracing.langsmith import annotate_current_run, traceable

logger = get_logger(__name__)


def _llm_trace_inputs(inputs: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": inputs.get("system_prompt", "")},
            {"role": "user", "content": inputs.get("user_prompt", "")},
        ],
        "temperature": inputs.get("temperature"),
        "max_tokens": inputs.get("max_tokens"),
    }


def _llm_trace_outputs(output) -> dict:
    if output is None:
        return {}
    content = output if isinstance(output, str) else str(output)
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class GroqClientError(RuntimeError):
    """Raised for missing config or a failed/malformed Groq API call."""


class GroqClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        if not self.settings.groq_api_key:
            raise GroqClientError("GROQ_API_KEY is not configured.")

    @traceable(
        name="groq_chat",
        run_type="llm",
        metadata={"ls_provider": "groq"},
        process_inputs=_llm_trace_inputs,
        process_outputs=_llm_trace_outputs,
    )
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> str:

        annotate_current_run(metadata={"ls_model_name": self.settings.groq_model})

        url = (
            f"{self.settings.groq_base_url.rstrip('/')}"
            "/chat/completions"
        )

        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=60,
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            body = getattr(exc.response, "text", "")

            raise GroqClientError(
                f"Groq API request failed: {exc}. {body}"
            ) from exc

        try:
            data = response.json()

            return data["choices"][0]["message"]["content"].strip()

        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GroqClientError(
                f"Unexpected Groq API response shape: {response.text[:500]}"
            ) from exc