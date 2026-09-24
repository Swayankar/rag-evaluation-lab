import requests

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GroqClientError(RuntimeError):
    """Raised for missing config or a failed/malformed Groq API call."""


class GroqClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

        if not self.settings.groq_api_key:
            raise GroqClientError("GROQ_API_KEY is not configured.")

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 800,
    ) -> str:

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
                f"Unexpected Groq API response shape: {data}"
            ) from exc