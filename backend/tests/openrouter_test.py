"""Unit tests for OpenRouter support in the AI settings service (docs/10).

These exercise the pure service helpers (credential resolution, live model
listing, connection test) with the OpenRouter network call mocked out — they do
NOT require the dev DB and never hit the real OpenRouter API.

    cd backend; uv run pytest tests/openrouter_test.py
"""

from __future__ import annotations

from types import SimpleNamespace

import openai

from app.modules.ai.providers import PROVIDER_REGISTRY, get_provider
from app.modules.integrations import service


class _FakeModels:
    def __init__(self, data: list) -> None:
        self._data = data

    async def list(self):
        return SimpleNamespace(data=self._data)


class _FakeAsyncOpenAI:
    """Stand-in for ``openai.AsyncOpenAI`` that records constructor kwargs."""

    last_kwargs: dict = {}

    def __init__(self, *, data: list, **kwargs):
        type(self).last_kwargs = kwargs
        self.models = _FakeModels(data)


def _patch_openai(monkeypatch, data: list) -> type[_FakeAsyncOpenAI]:
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kw: _FakeAsyncOpenAI(data=data, **kw))
    return _FakeAsyncOpenAI


def _raise_openai(monkeypatch) -> None:
    def boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(openai, "AsyncOpenAI", boom)


# ── Registry + managed providers ────────────────────────────────────────────────


def test_openrouter_registered_and_managed():
    assert "openrouter" in service.MANAGED_PROVIDERS
    spec = get_provider("openrouter")
    assert spec is not None
    assert spec.label == "OpenRouter"
    assert spec.api_key_field == "openrouter_api_key"
    # Catalog is fetched live, so the static registry list is empty.
    assert PROVIDER_REGISTRY["openrouter"].models == []


# ── Credential resolution ─────────────────────────────────────────────────────────


def test_provider_creds_defaults_to_public_base_url(monkeypatch):
    monkeypatch.setattr(service.settings, "openrouter_api_key", None, raising=False)
    monkeypatch.setattr(service.settings, "openrouter_base_url", None, raising=False)
    api_key, base_url = service._provider_creds({}, "openrouter")
    assert api_key is None
    assert base_url == service.OPENROUTER_BASE_URL


def test_provider_creds_falls_back_to_settings(monkeypatch):
    monkeypatch.setattr(service.settings, "openrouter_api_key", "env-key", raising=False)
    monkeypatch.setattr(
        service.settings, "openrouter_base_url", "https://gw.example/v1", raising=False
    )
    api_key, base_url = service._provider_creds({}, "openrouter")
    assert api_key == "env-key"
    assert base_url == "https://gw.example/v1"


def test_provider_creds_config_overrides_settings(monkeypatch):
    monkeypatch.setattr(service.settings, "openrouter_api_key", "env-key", raising=False)
    config = {"providers": {"openrouter": {"api_key": "tenant-key", "base_url": "https://x/v1"}}}
    api_key, base_url = service._provider_creds(config, "openrouter")
    assert api_key == "tenant-key"
    assert base_url == "https://x/v1"


# ── list_models ─────────────────────────────────────────────────────────────────


async def test_list_models_openrouter_live_sorted(monkeypatch):
    data = [
        SimpleNamespace(id="openai/gpt-4o", name="OpenAI: GPT-4o"),
        SimpleNamespace(id="anthropic/claude-3.5-sonnet", name="Anthropic: Claude 3.5 Sonnet"),
        SimpleNamespace(id="google/gemini-2.0-flash"),  # no name -> falls back to id
    ]
    _patch_openai(monkeypatch, data)
    models = await service.list_models(
        "openrouter", api_key="sk-or-123", base_url=service.OPENROUTER_BASE_URL
    )
    assert {"id": "anthropic/claude-3.5-sonnet", "name": "Anthropic: Claude 3.5 Sonnet"} in models
    # Provider-namespaced id preserved; name defaults to id when absent.
    assert {"id": "google/gemini-2.0-flash", "name": "google/gemini-2.0-flash"} in models
    # Sorted case-insensitively by display name/id.
    names = [m["name"] for m in models]
    assert names == sorted(names, key=str.lower)


async def test_list_models_openrouter_without_key_sends_placeholder(monkeypatch):
    data = [SimpleNamespace(id="openai/gpt-4o", name="OpenAI: GPT-4o")]
    _patch_openai(monkeypatch, data)
    models = await service.list_models("openrouter", api_key=None, base_url=None)
    assert models == [{"id": "openai/gpt-4o", "name": "OpenAI: GPT-4o"}]
    # No configured key -> a placeholder is sent and the default base URL is used.
    assert _FakeAsyncOpenAI.last_kwargs["base_url"] == service.OPENROUTER_BASE_URL
    assert _FakeAsyncOpenAI.last_kwargs["api_key"]


async def test_list_models_openrouter_falls_back_on_error(monkeypatch):
    _raise_openai(monkeypatch)
    models = await service.list_models(
        "openrouter", api_key="sk-or-123", base_url=service.OPENROUTER_BASE_URL
    )
    # Registry list for openrouter is empty -> empty fallback, no exception.
    assert models == []


# ── test_connection ────────────────────────────────────────────────────────────


async def test_test_connection_openrouter_success(monkeypatch):
    data = [SimpleNamespace(id=f"p/m{i}") for i in range(3)]
    _patch_openai(monkeypatch, data)
    result = await service.test_connection(
        "openrouter", api_key="sk-or-123", base_url=service.OPENROUTER_BASE_URL
    )
    assert result["success"] is True
    assert "OpenRouter" in result["message"]
    assert "3 models" in result["message"]


async def test_test_connection_openrouter_failure(monkeypatch):
    _raise_openai(monkeypatch)
    result = await service.test_connection(
        "openrouter", api_key="sk-or-123", base_url=service.OPENROUTER_BASE_URL
    )
    assert result["success"] is False
    assert "Connection failed" in result["message"]


async def test_test_connection_openrouter_requires_key():
    result = await service.test_connection("openrouter", api_key=None, base_url=None)
    assert result["success"] is False
    assert "No API key" in result["message"]
