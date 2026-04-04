"""Tests for the LLM client with mocked HTTP responses."""

import json
import pytest
import httpx

from core.llm_client import LLMClient


class MockTransport(httpx.BaseTransport):
    """Mock transport that returns configured responses."""

    def __init__(self, handler):
        self.handler = handler

    def handle_request(self, request):
        return self.handler(request)


def make_client_with_mock(handler, timeout=30.0):
    """Create an LLMClient that uses a mock transport."""
    client = LLMClient(timeout=timeout)
    # Monkey-patch to inject mock transport
    original_expand = client.expand

    def patched_expand(text, provider, endpoint, model, system_prompt, temperature, api_key=""):
        # Override httpx.Client to use mock transport
        original_client_init = httpx.Client.__init__

        def mock_init(self_client, **kwargs):
            kwargs["transport"] = MockTransport(handler)
            kwargs.pop("timeout", None)
            original_client_init(self_client, timeout=timeout, **kwargs)

        httpx.Client.__init__ = mock_init
        try:
            return original_expand(text, provider, endpoint, model, system_prompt, temperature, api_key)
        finally:
            httpx.Client.__init__ = original_client_init

    client.expand = patched_expand
    return client


class TestOllamaProvider:
    def test_successful_expansion(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["model"] == "llama3.2"
            assert body["stream"] is False
            return httpx.Response(200, json={"response": "enhanced warrior prompt"})

        client = make_client_with_mock(handler)
        result = client.expand(
            "a warrior", "ollama", "http://localhost:11434",
            "llama3.2", "enhance this", 0.7,
        )
        assert result == "enhanced warrior prompt"

    def test_empty_response_passthrough(self):
        def handler(request):
            return httpx.Response(200, json={"response": ""})

        client = make_client_with_mock(handler)
        result = client.expand(
            "original text", "ollama", "http://localhost:11434",
            "llama3.2", "enhance", 0.7,
        )
        assert result == "original text"


class TestOpenAIProvider:
    def test_successful_expansion(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["model"] == "gpt-4"
            assert len(body["messages"]) == 2
            assert body["messages"][0]["role"] == "system"
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "enhanced prompt"}}]
            })

        client = make_client_with_mock(handler)
        result = client.expand(
            "a scene", "openai_compatible", "http://localhost:8080",
            "gpt-4", "enhance", 0.7, api_key="test-key",
        )
        assert result == "enhanced prompt"

    def test_auth_header_sent(self):
        def handler(request):
            assert request.headers.get("authorization") == "Bearer my-key"
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}}]
            })

        client = make_client_with_mock(handler)
        client.expand(
            "text", "openai_compatible", "http://localhost:8080",
            "model", "sys", 0.7, api_key="my-key",
        )

    def test_malformed_response_passthrough(self):
        def handler(request):
            return httpx.Response(200, json={"unexpected": "format"})

        client = make_client_with_mock(handler)
        result = client.expand(
            "original", "openai_compatible", "http://localhost:8080",
            "model", "sys", 0.7,
        )
        assert result == "original"


class TestAnthropicProvider:
    def test_successful_expansion(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["model"] == "claude-sonnet-4-20250514"
            assert body["max_tokens"] == 1024
            assert request.headers.get("x-api-key") == "sk-ant-test"
            assert request.headers.get("anthropic-version") == "2023-06-01"
            return httpx.Response(200, json={
                "content": [{"type": "text", "text": "enhanced by claude"}]
            })

        client = make_client_with_mock(handler)
        result = client.expand(
            "a warrior", "anthropic", "https://api.anthropic.com",
            "claude-sonnet-4-20250514", "enhance", 0.7, api_key="sk-ant-test",
        )
        assert result == "enhanced by claude"


class TestErrorHandling:
    def test_connection_refused(self):
        client = LLMClient(timeout=2.0)
        # Use a port that's almost certainly not listening
        result = client.expand(
            "original text", "ollama", "http://127.0.0.1:19999",
            "model", "sys", 0.7,
        )
        assert result == "original text"

    def test_http_error_passthrough(self):
        def handler(request):
            return httpx.Response(401, text="Unauthorized")

        client = make_client_with_mock(handler)
        result = client.expand(
            "original text", "openai_compatible", "http://localhost:8080",
            "model", "sys", 0.7, api_key="bad-key",
        )
        assert result == "original text"

    def test_http_500_passthrough(self):
        def handler(request):
            return httpx.Response(500, text="Internal Server Error")

        client = make_client_with_mock(handler)
        result = client.expand(
            "original text", "ollama", "http://localhost:11434",
            "model", "sys", 0.7,
        )
        assert result == "original text"

    def test_invalid_json_passthrough(self):
        def handler(request):
            return httpx.Response(200, text="not json at all")

        client = make_client_with_mock(handler)
        result = client.expand(
            "original text", "ollama", "http://localhost:11434",
            "model", "sys", 0.7,
        )
        assert result == "original text"

    def test_unknown_provider_passthrough(self):
        client = LLMClient()
        result = client.expand(
            "original text", "unknown_provider", "http://localhost",
            "model", "sys", 0.7,
        )
        assert result == "original text"
