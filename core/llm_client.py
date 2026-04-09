"""HTTP client for LLM provider communication.

Supports Ollama, OpenAI-compatible, and Anthropic APIs via plain HTTP.
No provider-specific SDK dependencies. No ComfyUI dependencies.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("PromptAlchemy")

DEFAULT_TIMEOUT = 30.0  # seconds


class LLMClient:
    """Synchronous HTTP client for LLM text expansion."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def expand(
        self,
        text: str,
        provider: str,
        endpoint: str,
        model: str,
        system_prompt: str,
        temperature: float,
        api_key: str = "",
    ) -> str:
        """Send text to an LLM and return the expanded result.

        Raises on failure so the caller (ComfyUI node) surfaces a visible error.
        """
        if provider == "ollama":
            return self._call_ollama(text, endpoint, model, system_prompt, temperature)
        elif provider == "openai_compatible":
            return self._call_openai(text, endpoint, model, system_prompt, temperature, api_key)
        elif provider == "anthropic":
            return self._call_anthropic(text, endpoint, model, system_prompt, temperature, api_key)
        else:
            raise ValueError(f"PA LLM Expander: unknown provider {provider!r}")

    def _call_ollama(
        self, text: str, endpoint: str, model: str,
        system_prompt: str, temperature: float,
    ) -> str:
        url = f"{endpoint.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": text,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            if not response.is_success:
                body = response.text[:300]
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code} from Ollama: {body}",
                    request=response.request,
                    response=response,
                )
            data = response.json()

        result = data.get("response", "").strip()
        if not result:
            logger.warning("PA LLM Expander: Ollama returned empty response, passing through")
            return text
        return result

    def _call_openai(
        self, text: str, endpoint: str, model: str,
        system_prompt: str, temperature: float, api_key: str,
    ) -> str:
        url = f"{endpoint.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            result = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            logger.warning(
                "PA LLM Expander: unexpected OpenAI response format: %s",
                str(data)[:300],
            )
            return text

        if not result:
            logger.warning("PA LLM Expander: OpenAI returned empty response, passing through")
            return text
        return result

    def _call_anthropic(
        self, text: str, endpoint: str, model: str,
        system_prompt: str, temperature: float, api_key: str,
    ) -> str:
        url = f"{endpoint.rstrip('/')}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            result = data["content"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            logger.warning(
                "PA LLM Expander: unexpected Anthropic response format: %s",
                str(data)[:300],
            )
            return text

        if not result:
            logger.warning("PA LLM Expander: Anthropic returned empty response, passing through")
            return text
        return result
