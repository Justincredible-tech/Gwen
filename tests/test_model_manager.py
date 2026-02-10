"""Tests for gwen.core.model_manager — Ollama integration and adaptive profiles.

Run unit tests (no Ollama required):
    pytest tests/test_model_manager.py -v -k "not ollama"

Run ALL tests including Ollama integration:
    pytest tests/test_model_manager.py -v
"""

import asyncio
import json
import unittest.mock
import urllib.request
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from gwen.core.model_manager import (
    AdaptiveModelManager,
    OllamaClient,
    detect_profile,
)
from gwen.models.classification import HardwareProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(body: dict) -> MagicMock:
    """Create a mock urllib response that returns JSON."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: OllamaClient (unit — mocked HTTP)
# ---------------------------------------------------------------------------

class TestOllamaClient:
    """Unit tests for OllamaClient with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_generate_returns_response_text(self) -> None:
        """generate() should extract the 'response' field from Ollama JSON."""
        client = OllamaClient(host="http://localhost:11434")
        mock_resp = _make_mock_response({"response": "Hello from Ollama!"})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await client.generate(
                model="qwen3:0.6b", prompt="Say hello"
            )

        assert result == "Hello from Ollama!"

    @pytest.mark.asyncio
    async def test_generate_sends_correct_payload(self) -> None:
        """generate() should POST the correct JSON to /api/generate."""
        client = OllamaClient(host="http://localhost:11434")
        mock_resp = _make_mock_response({"response": "ok"})

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            await client.generate(
                model="qwen3:0.6b",
                prompt="Test prompt",
                system="You are helpful",
                format="json",
            )

        # Verify the request was made
        mock_open.assert_called_once()
        call_args = mock_open.call_args
        request_obj = call_args[0][0]
        sent_body = json.loads(request_obj.data.decode("utf-8"))
        assert sent_body["model"] == "qwen3:0.6b"
        assert sent_body["prompt"] == "Test prompt"
        assert sent_body["system"] == "You are helpful"
        assert sent_body["format"] == "json"
        assert sent_body["stream"] is False

    @pytest.mark.asyncio
    async def test_embed_returns_first_vector(self) -> None:
        """embed() should return the first embedding vector."""
        client = OllamaClient(host="http://localhost:11434")
        fake_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_resp = _make_mock_response({"embeddings": [fake_vector]})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await client.embed(model="qwen3-embedding:0.6b", text="hello")

        assert result == fake_vector

    @pytest.mark.asyncio
    async def test_list_models_returns_model_list(self) -> None:
        """list_models() should return the 'models' array from /api/tags."""
        client = OllamaClient(host="http://localhost:11434")
        models_data = [
            {"name": "qwen3:0.6b", "size": 400000000},
            {"name": "qwen3:8b", "size": 5000000000},
        ]
        mock_resp = _make_mock_response({"models": models_data})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await client.list_models()

        assert len(result) == 2
        assert result[0]["name"] == "qwen3:0.6b"

    @pytest.mark.asyncio
    async def test_list_running_returns_running_models(self) -> None:
        """list_running() should return the 'models' array from /api/ps."""
        client = OllamaClient(host="http://localhost:11434")
        running_data = [
            {"name": "qwen3:0.6b", "size_vram": 400000000},
        ]
        mock_resp = _make_mock_response({"models": running_data})

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await client.list_running()

        assert len(result) == 1
        assert result[0]["name"] == "qwen3:0.6b"

    @pytest.mark.asyncio
    async def test_connection_error_on_unreachable_host(self) -> None:
        """Client should raise ConnectionError if Ollama is not running."""
        import urllib.error

        client = OllamaClient(host="http://localhost:99999")

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with pytest.raises(ConnectionError, match="Cannot reach Ollama"):
                await client.generate(model="qwen3:0.6b", prompt="test")


# ---------------------------------------------------------------------------
# Tests: detect_profile (unit — mocked HTTP)
# ---------------------------------------------------------------------------

class TestDetectProfile:
    """Unit tests for detect_profile() with mocked Ollama responses."""

    @pytest.mark.asyncio
    async def test_pocket_profile_low_vram(self) -> None:
        """< 6GB VRAM should return POCKET."""
        # 4 GB in bytes
        vram_bytes = 4 * (1024 ** 3)
        running_resp = _make_mock_response({
            "models": [{"name": "qwen3:0.6b", "size_vram": vram_bytes}]
        })

        with patch("urllib.request.urlopen", return_value=running_resp):
            profile = await detect_profile()

        assert profile == HardwareProfile.POCKET

    @pytest.mark.asyncio
    async def test_portable_profile_medium_vram(self) -> None:
        """8GB VRAM should return PORTABLE."""
        vram_bytes = 8 * (1024 ** 3)
        running_resp = _make_mock_response({
            "models": [{"name": "qwen3:0.6b", "size_vram": vram_bytes}]
        })

        with patch("urllib.request.urlopen", return_value=running_resp):
            profile = await detect_profile()

        assert profile == HardwareProfile.PORTABLE

    @pytest.mark.asyncio
    async def test_standard_profile_high_vram(self) -> None:
        """16GB VRAM should return STANDARD."""
        vram_bytes = 16 * (1024 ** 3)
        running_resp = _make_mock_response({
            "models": [{"name": "qwen3:8b", "size_vram": vram_bytes}]
        })

        with patch("urllib.request.urlopen", return_value=running_resp):
            profile = await detect_profile()

        assert profile == HardwareProfile.STANDARD

    @pytest.mark.asyncio
    async def test_power_profile_very_high_vram(self) -> None:
        """24GB VRAM should return POWER."""
        vram_bytes = 24 * (1024 ** 3)
        running_resp = _make_mock_response({
            "models": [{"name": "qwen3:8b", "size_vram": vram_bytes}]
        })

        with patch("urllib.request.urlopen", return_value=running_resp):
            profile = await detect_profile()

        assert profile == HardwareProfile.POWER

    @pytest.mark.asyncio
    async def test_fallback_to_portable_on_connection_error(self) -> None:
        """If Ollama is unreachable, default to PORTABLE."""
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            profile = await detect_profile()

        assert profile == HardwareProfile.PORTABLE

    @pytest.mark.asyncio
    async def test_no_running_models_probes_with_smallest(self) -> None:
        """When no models are running, detect_profile should probe VRAM."""
        call_count = 0
        vram_bytes = 8 * (1024 ** 3)

        def mock_urlopen(req, **kwargs):
            nonlocal call_count
            call_count += 1

            # Decode the request to determine which endpoint is called
            if isinstance(req, urllib.request.Request):
                url = req.full_url
            else:
                url = req

            if "/api/ps" in url:
                if call_count <= 1:
                    # First call: no models running
                    return _make_mock_response({"models": []})
                else:
                    # After loading probe model
                    return _make_mock_response({
                        "models": [
                            {"name": "qwen3:0.6b", "size_vram": vram_bytes}
                        ]
                    })
            elif "/api/generate" in url:
                # load_model or unload_model call
                return _make_mock_response({"response": ""})
            else:
                return _make_mock_response({})

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            profile = await detect_profile()

        assert profile == HardwareProfile.PORTABLE


# ---------------------------------------------------------------------------
# Tests: AdaptiveModelManager (unit — no Ollama needed)
# ---------------------------------------------------------------------------

class TestAdaptiveModelManager:
    """Unit tests for AdaptiveModelManager with mocked OllamaClient."""

    def test_get_model_for_tier_pocket(self) -> None:
        """Pocket profile should map all tiers to qwen3:0.6b."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POCKET, ollama_host="http://fake:11434"
        )
        assert mgr.get_model_for_tier(0) == "qwen3:0.6b"
        assert mgr.get_model_for_tier(1) == "qwen3:0.6b"
        assert mgr.get_model_for_tier(2) == "qwen3:0.6b"

    def test_get_model_for_tier_portable(self) -> None:
        """Portable profile should use 0.6b for Tier 0 and 8b-q3 for 1+2."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.PORTABLE, ollama_host="http://fake:11434"
        )
        assert mgr.get_model_for_tier(0) == "qwen3:0.6b"
        assert mgr.get_model_for_tier(1) == "qwen3:8b-q3"
        assert mgr.get_model_for_tier(2) == "qwen3:8b-q3"

    def test_get_model_for_tier_standard(self) -> None:
        """Standard profile should use 0.6b, 8b, and 30b."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.STANDARD, ollama_host="http://fake:11434"
        )
        assert mgr.get_model_for_tier(0) == "qwen3:0.6b"
        assert mgr.get_model_for_tier(1) == "qwen3:8b"
        assert mgr.get_model_for_tier(2) == "qwen3-coder:30b"

    def test_get_model_for_tier_power(self) -> None:
        """Power profile should use 0.6b, 8b, and 30b (same as standard)."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POWER, ollama_host="http://fake:11434"
        )
        assert mgr.get_model_for_tier(0) == "qwen3:0.6b"
        assert mgr.get_model_for_tier(1) == "qwen3:8b"
        assert mgr.get_model_for_tier(2) == "qwen3-coder:30b"

    def test_invalid_tier_raises_value_error(self) -> None:
        """Requesting tier 3 or -1 should raise ValueError."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POCKET, ollama_host="http://fake:11434"
        )
        with pytest.raises(ValueError, match="Invalid tier"):
            mgr.get_model_for_tier(3)
        with pytest.raises(ValueError, match="Invalid tier"):
            mgr.get_model_for_tier(-1)

    @pytest.mark.asyncio
    async def test_ensure_tier_loaded_pocket_unloads_others(self) -> None:
        """Pocket profile should unload all other models before loading."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POCKET, ollama_host="http://fake:11434"
        )
        # Mock the client methods
        mgr.client.list_running = AsyncMock(return_value=[])
        mgr.client.load_model = AsyncMock()
        mgr.client.unload_model = AsyncMock()

        await mgr.ensure_tier_loaded(0)

        mgr.client.load_model.assert_called_once_with("qwen3:0.6b")
        assert 0 in mgr._loaded_tiers

    @pytest.mark.asyncio
    async def test_ensure_tier_loaded_standard_time_shares_tier2(self) -> None:
        """Standard profile should unload Tier 1 when loading Tier 2."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.STANDARD, ollama_host="http://fake:11434"
        )
        mgr.client.load_model = AsyncMock()
        mgr.client.unload_model = AsyncMock()
        mgr.client.list_running = AsyncMock(return_value=[])

        # First load Tier 1
        await mgr.ensure_tier_loaded(1)
        assert 1 in mgr._loaded_tiers

        # Now load Tier 2 — should unload Tier 1 first
        await mgr.ensure_tier_loaded(2)
        mgr.client.unload_model.assert_called_with("qwen3:8b")
        assert 1 not in mgr._loaded_tiers
        assert 2 in mgr._loaded_tiers

    @pytest.mark.asyncio
    async def test_ensure_tier_loaded_power_loads_all(self) -> None:
        """Power profile should load Tier 2 without unloading anything."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POWER, ollama_host="http://fake:11434"
        )
        mgr.client.load_model = AsyncMock()
        mgr.client.unload_model = AsyncMock()

        await mgr.ensure_tier_loaded(0)
        await mgr.ensure_tier_loaded(1)
        await mgr.ensure_tier_loaded(2)

        # unload_model should NOT have been called
        mgr.client.unload_model.assert_not_called()
        assert mgr._loaded_tiers == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_generate_calls_correct_model(self) -> None:
        """generate(tier=1) should call OllamaClient with the tier's model."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.STANDARD, ollama_host="http://fake:11434"
        )
        mgr.client.generate = AsyncMock(return_value="Test response")

        result = await mgr.generate(tier=1, prompt="Hello")

        mgr.client.generate.assert_called_once_with(
            model="qwen3:8b",
            prompt="Hello",
            system=None,
            format=None,
            options=None,
        )
        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_embed_uses_embedding_model(self) -> None:
        """embed() should always use qwen3-embedding:0.6b."""
        mgr = AdaptiveModelManager(
            profile=HardwareProfile.POCKET, ollama_host="http://fake:11434"
        )
        fake_vector = [0.1] * 1024
        mgr.client.embed = AsyncMock(return_value=fake_vector)

        result = await mgr.embed("test text")

        mgr.client.embed.assert_called_once_with(
            model="qwen3-embedding:0.6b",
            text="test text",
        )
        assert len(result) == 1024

    def test_concurrency_settings_match_srs(self) -> None:
        """Verify CONCURRENCY dict matches SRS.md Section 3.16."""
        assert AdaptiveModelManager.CONCURRENCY[HardwareProfile.POCKET] == {
            "max_concurrent": 1, "tier2_strategy": "inline"
        }
        assert AdaptiveModelManager.CONCURRENCY[HardwareProfile.PORTABLE] == {
            "max_concurrent": 2, "tier2_strategy": "time_share"
        }
        assert AdaptiveModelManager.CONCURRENCY[HardwareProfile.STANDARD] == {
            "max_concurrent": 2, "tier2_strategy": "time_share"
        }
        assert AdaptiveModelManager.CONCURRENCY[HardwareProfile.POWER] == {
            "max_concurrent": 3, "tier2_strategy": "concurrent"
        }


# ---------------------------------------------------------------------------
# Integration test — requires a running Ollama instance
# ---------------------------------------------------------------------------

@pytest.mark.ollama
class TestOllamaIntegration:
    """Integration tests that require a running Ollama server.

    Skip these in CI or when Ollama is not available:
        pytest tests/test_model_manager.py -v -k "not ollama"

    To run:
        pytest tests/test_model_manager.py -v -m ollama
    """

    @pytest.mark.asyncio
    async def test_generate_tier0_returns_text(self) -> None:
        """Tier 0 (qwen3:0.6b) should return a non-empty text response.

        Prerequisite: ``ollama pull qwen3:0.6b`` must have been run.
        """
        mgr = AdaptiveModelManager(profile=HardwareProfile.POCKET)
        await mgr.ensure_tier_loaded(0)
        result = await mgr.generate(
            tier=0,
            prompt="Say exactly: HELLO WORLD",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_detect_profile_returns_valid_enum(self) -> None:
        """detect_profile() should return a valid HardwareProfile."""
        profile = await detect_profile()
        assert isinstance(profile, HardwareProfile)

    @pytest.mark.asyncio
    async def test_embed_returns_vector(self) -> None:
        """embed() should return a list of floats.

        Prerequisite: ``ollama pull qwen3-embedding:0.6b`` must have been run.
        """
        mgr = AdaptiveModelManager(profile=HardwareProfile.POCKET)
        vector = await mgr.embed("Hello world")
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)
