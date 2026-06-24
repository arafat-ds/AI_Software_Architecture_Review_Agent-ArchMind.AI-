"""Unit tests for api/dependencies.py — singleton dependency providers.

Covers:
  - Lazy initialization on first call.
  - Singleton: repeated calls return the same instance.
  - Executor max_workers sourced from settings.max_concurrent_jobs.
  - shutdown_executor(): clears module-level singleton, safe when not yet initialized.

SupabaseClient and get_settings are patched — no real Supabase connection or
environment variables are required.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

import api.dependencies as deps

_SETTINGS_PATCH = "api.dependencies.get_settings"
_CLIENT_PATCH = "api.dependencies.SupabaseClient"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module-level singletons before and after each test."""
    deps._supabase_client = None
    deps._orchestrator = None
    deps._executor = None
    yield
    if deps._executor is not None:
        deps._executor.shutdown(wait=False)
    deps._supabase_client = None
    deps._orchestrator = None
    deps._executor = None


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.supabase_url = "https://fake.supabase.co"
    settings.supabase_key = "fake-service-key"
    settings.max_concurrent_jobs = 2
    return settings


# ---------------------------------------------------------------------------
# get_supabase_client
# ---------------------------------------------------------------------------


def test_get_supabase_client_returns_supabase_client_instance(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch(_CLIENT_PATCH) as MockClient:
        client = deps.get_supabase_client()
        assert client is MockClient.return_value


def test_get_supabase_client_returns_singleton_on_repeated_calls(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch(_CLIENT_PATCH) as MockClient:
        c1 = deps.get_supabase_client()
        c2 = deps.get_supabase_client()
        assert c1 is c2
        MockClient.assert_called_once()


# ---------------------------------------------------------------------------
# get_orchestrator
# ---------------------------------------------------------------------------


def test_get_orchestrator_returns_analysis_orchestrator_instance(mock_settings):
    from services.orchestrator import AnalysisOrchestrator
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch(_CLIENT_PATCH):
        orchestrator = deps.get_orchestrator()
        assert isinstance(orchestrator, AnalysisOrchestrator)


def test_get_orchestrator_returns_singleton_on_repeated_calls(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings), \
         patch(_CLIENT_PATCH):
        o1 = deps.get_orchestrator()
        o2 = deps.get_orchestrator()
        assert o1 is o2


# ---------------------------------------------------------------------------
# get_executor
# ---------------------------------------------------------------------------


def test_get_executor_returns_thread_pool_executor_instance(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        executor = deps.get_executor()
        assert isinstance(executor, ThreadPoolExecutor)


def test_get_executor_returns_singleton_on_repeated_calls(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        e1 = deps.get_executor()
        e2 = deps.get_executor()
        assert e1 is e2


def test_get_executor_max_workers_matches_settings_max_concurrent_jobs(mock_settings):
    mock_settings.max_concurrent_jobs = 3
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        executor = deps.get_executor()
        assert executor._max_workers == 3


# ---------------------------------------------------------------------------
# shutdown_executor
# ---------------------------------------------------------------------------


def test_shutdown_executor_cleans_up_and_resets_to_none(mock_settings):
    with patch(_SETTINGS_PATCH, return_value=mock_settings):
        deps.get_executor()
    assert deps._executor is not None
    deps.shutdown_executor()
    assert deps._executor is None


def test_shutdown_executor_safe_when_executor_not_initialized():
    assert deps._executor is None
    deps.shutdown_executor()  # must not raise
