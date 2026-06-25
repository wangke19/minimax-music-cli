import requests

from ..config import ANTHROPIC_API_BASE_URL, ANTHROPIC_MODEL_DEFAULT


class AnthropicClient:
    """Raw HTTP client for Anthropic Messages API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = ANTHROPIC_API_BASE_URL,
        api_version: str = "2023-06-01",
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version
        self._session = requests.Session()
        self._session.headers.update({
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": api_version,
        })

    def generate_text(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        model: str = ANTHROPIC_MODEL_DEFAULT,
        temperature: float = 0.7,
        timeout: int = 60,
    ) -> str:
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = self._session.post(
            f"{self._base_url}/messages",
            json=payload,
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise Exception(f"Anthropic API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        content_blocks = data.get("content", [])
        if not content_blocks:
            raise Exception("Anthropic API returned empty content")

        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        text = "".join(text_parts).strip()
        if not text:
            raise Exception("Anthropic API returned empty text")
        return text
