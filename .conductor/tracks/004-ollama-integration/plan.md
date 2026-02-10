# Plan: Ollama Integration

**Track:** 004-ollama-integration
**Depends on:** 001-project-scaffold (gwen package must be importable)
**Produces:** gwen/core/__init__.py, gwen/core/model_manager.py, tests/test_model_manager.py

---

## Phase 1: Ollama HTTP Client

### Step 1.1: Create gwen/core/__init__.py

Create the file `gwen/core/__init__.py` with the following exact content:

```python
"""Core services — orchestrator, model manager, session manager."""
```

**Why:** This makes `gwen.core` a Python package so that `from gwen.core.model_manager import AdaptiveModelManager` works.

---

### Step 1.2: Create gwen/core/model_manager.py with the OllamaClient helper

Create the file `gwen/core/model_manager.py` with the following exact content. This step defines the low-level HTTP client that talks to the Ollama REST API. The AdaptiveModelManager is added in Phase 3.

**IMPORTANT:** We use `urllib.request` (stdlib) for HTTP, NOT the `requests` library. The `requests` library is not in tech-stack.md and therefore must not be used. Because `urllib.request` is synchronous, every blocking HTTP call is wrapped in `asyncio.to_thread()` so it can be called from async code without blocking the event loop.

```python
"""
AdaptiveModelManager — maps logical tiers to physical Ollama models.

The orchestrator never references specific model names. It requests a
logical tier (0, 1, 2) and this module provides the appropriate physical
model based on detected hardware capabilities.

References: SRS.md Sections 2.2, 3.16, FR-ORCH-001.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hardware Profile enum
# ---------------------------------------------------------------------------
# This enum is also defined in gwen/models/ (track 002). Once track 002 is
# complete, this definition should be replaced with an import:
#     from gwen.models.classification import HardwareProfile
# For now we define it here so that track 004 can be developed independently.

class HardwareProfile(Enum):
    """Hardware capability tier, auto-detected at startup."""
    POCKET = "pocket"       # Phone / low-end: 1 model plays all 3 roles
    PORTABLE = "portable"   # Laptop 8GB VRAM: 0.6B + 8B-Q3
    STANDARD = "standard"   # Desktop 12-16GB VRAM: 0.6B + 8B + 30B time-shared
    POWER = "power"         # Workstation 24GB+ VRAM: all tiers concurrent


# ---------------------------------------------------------------------------
# OllamaClient — low-level HTTP wrapper
# ---------------------------------------------------------------------------

class OllamaClient:
    """Synchronous HTTP client for the Ollama REST API.

    All public methods are async.  Internally they use
    ``asyncio.to_thread`` to run blocking ``urllib.request`` calls
    without stalling the event loop.
    """

    def __init__(self, host: str = "http://localhost:11434") -> None:
        """Initialise the client.

        Parameters
        ----------
        host : str
            Base URL for the Ollama server (no trailing slash).
        """
        self.host = host.rstrip("/")

    # -- internal helpers ---------------------------------------------------

    def _post_sync(self, path: str, payload: dict) -> dict:
        """Send a POST request and return the parsed JSON response.

        Parameters
        ----------
        path : str
            API path, e.g. ``/api/generate``.
        payload : dict
            JSON-serialisable body.

        Returns
        -------
        dict
            Parsed JSON response.

        Raises
        ------
        ConnectionError
            If Ollama is not reachable.
        """
        url = f"{self.host}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.host}: {exc}"
            ) from exc

    def _get_sync(self, path: str) -> dict:
        """Send a GET request and return the parsed JSON response.

        Parameters
        ----------
        path : str
            API path, e.g. ``/api/tags``.

        Returns
        -------
        dict
            Parsed JSON response.
        """
        url = f"{self.host}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.host}: {exc}"
            ) from exc

    # -- public async API ---------------------------------------------------

    async def generate(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        format: Optional[str] = None,
        stream: bool = False,
        options: Optional[dict] = None,
    ) -> str:
        """Generate a completion from an Ollama model.

        Parameters
        ----------
        model : str
            Physical model name, e.g. ``"qwen3:0.6b"``.
        prompt : str
            The user prompt to send.
        system : str | None
            Optional system prompt.
        format : str | None
            Set to ``"json"`` to request JSON-formatted output.
        stream : bool
            Must be ``False`` (streaming not supported in this client).
        options : dict | None
            Optional model parameters (temperature, top_p, etc.).

        Returns
        -------
        str
            The model's response text.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # always false — we read the full response
        }
        if system is not None:
            payload["system"] = system
        if format is not None:
            payload["format"] = format
        if options is not None:
            payload["options"] = options

        result = await asyncio.to_thread(self._post_sync, "/api/generate", payload)
        return result.get("response", "")

    async def embed(self, model: str, text: str) -> list[float]:
        """Compute an embedding vector for the given text.

        Parameters
        ----------
        model : str
            Embedding model name, e.g. ``"qwen3-embedding:0.6b"``.
        text : str
            Text to embed.

        Returns
        -------
        list[float]
            The embedding vector (e.g. 1024-dim for qwen3-embedding).
        """
        payload = {"model": model, "input": text}
        result = await asyncio.to_thread(self._post_sync, "/api/embed", payload)
        # Ollama returns {"embeddings": [[...]]} — we want the first vector.
        embeddings = result.get("embeddings", [[]])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return []

    async def list_models(self) -> list[dict]:
        """List all models available in Ollama.

        Returns
        -------
        list[dict]
            Each dict has keys like ``name``, ``size``, ``modified_at``.
        """
        result = await asyncio.to_thread(self._get_sync, "/api/tags")
        return result.get("models", [])

    async def show_model(self, model: str) -> dict:
        """Get detailed information about a specific model.

        Parameters
        ----------
        model : str
            Model name, e.g. ``"qwen3:0.6b"``.

        Returns
        -------
        dict
            Model metadata including parameters, template, system info.
        """
        payload = {"name": model}
        return await asyncio.to_thread(self._post_sync, "/api/show", payload)

    async def list_running(self) -> list[dict]:
        """List currently loaded (running) models.

        Returns
        -------
        list[dict]
            Each dict has keys like ``name``, ``size``, ``size_vram``.
            This is the ``/api/ps`` endpoint.
        """
        result = await asyncio.to_thread(self._get_sync, "/api/ps")
        return result.get("models", [])

    async def load_model(self, model: str, keep_alive: str = "10m") -> None:
        """Load a model into VRAM without generating any output.

        Parameters
        ----------
        model : str
            Model to load.
        keep_alive : str
            How long to keep the model loaded.  Defaults to ``"10m"``.
            Set to ``"0"`` to unload immediately after next request.

        Notes
        -----
        This sends an empty-prompt generate request, which forces Ollama
        to load the model into memory.
        """
        payload = {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": keep_alive,
        }
        await asyncio.to_thread(self._post_sync, "/api/generate", payload)
        logger.info("Loaded model %s (keep_alive=%s)", model, keep_alive)

    async def unload_model(self, model: str) -> None:
        """Unload a model from VRAM.

        Parameters
        ----------
        model : str
            Model to unload.

        Notes
        -----
        This sends an empty-prompt generate request with
        ``keep_alive=0``, which tells Ollama to unload the model
        immediately.
        """
        payload = {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": "0",
        }
        try:
            await asyncio.to_thread(self._post_sync, "/api/generate", payload)
            logger.info("Unloaded model %s", model)
        except ConnectionError:
            logger.warning("Could not unload %s — Ollama unreachable", model)
```

**What this does:**
- Wraps all six Ollama REST endpoints the system needs: `/api/generate`, `/api/embed`, `/api/tags`, `/api/show`, `/api/ps`, and the load/unload pattern.
- Every method is `async def` but calls `asyncio.to_thread()` internally because `urllib.request` is synchronous.
- Timeouts: 300 seconds for generate (LLMs can be slow), 30 seconds for metadata endpoints.
- All errors from urllib are caught and re-raised as `ConnectionError` with a human-readable message.

---

## Phase 2: Hardware Detection

### Step 2.1: Add detect_profile() static method

Append the following to `gwen/core/model_manager.py`, **below** the `OllamaClient` class but **above** the `AdaptiveModelManager` class (which you will add in Phase 3). This is a standalone async function:

```python
# ---------------------------------------------------------------------------
# Hardware detection
# ---------------------------------------------------------------------------

async def detect_profile(
    ollama_host: str = "http://localhost:11434",
) -> HardwareProfile:
    """Auto-detect the hardware profile by querying Ollama for GPU info.

    Detection strategy
    ------------------
    1. Call ``/api/ps`` to see currently loaded models and their VRAM usage.
    2. Call ``/api/tags`` to see available models (as a proxy for system capability).
    3. Parse the ``size_vram`` fields from running models to estimate total VRAM.
    4. If no models are running, attempt to load ``qwen3:0.6b`` briefly to
       observe the VRAM allocation reported by ``/api/ps``.

    VRAM thresholds
    ---------------
    - Less than 6 GB  -> POCKET
    - 6 GB to 11 GB   -> PORTABLE
    - 12 GB to 22 GB  -> STANDARD
    - 23 GB or more   -> POWER

    If Ollama is not reachable or detection fails for any reason, defaults
    to PORTABLE (a safe middle ground that avoids loading models too large
    for the hardware while still providing good quality).

    Parameters
    ----------
    ollama_host : str
        Ollama base URL.

    Returns
    -------
    HardwareProfile
        The detected (or fallback) profile.
    """
    client = OllamaClient(host=ollama_host)

    try:
        # Step 1: Check running models for VRAM info
        running = await client.list_running()

        total_vram_bytes = 0
        if running:
            for model_info in running:
                # Ollama reports size_vram in bytes
                vram = model_info.get("size_vram", 0)
                total_vram_bytes += vram

        # Step 2: If no models are running, try loading the smallest model
        # to probe VRAM capacity.
        if total_vram_bytes == 0:
            logger.info("No models running. Probing VRAM with qwen3:0.6b...")
            try:
                await client.load_model("qwen3:0.6b", keep_alive="30s")
                running = await client.list_running()
                for model_info in running:
                    vram = model_info.get("size_vram", 0)
                    total_vram_bytes += vram
                # Unload the probe model so we don't waste VRAM
                await client.unload_model("qwen3:0.6b")
            except ConnectionError:
                logger.warning("VRAM probe failed — using fallback profile")
                return HardwareProfile.PORTABLE

        # Step 3: If we still have no VRAM info, check if Ollama reports
        # system info through the models list (model file sizes as proxy).
        if total_vram_bytes == 0:
            models = await client.list_models()
            if models:
                # Use largest available model size as a rough proxy:
                # if they have a 30B model downloaded, they probably have
                # enough VRAM for STANDARD or higher.
                largest_size = max(m.get("size", 0) for m in models)
                if largest_size > 15_000_000_000:  # > 15GB model file
                    return HardwareProfile.STANDARD
                elif largest_size > 3_000_000_000:  # > 3GB model file
                    return HardwareProfile.PORTABLE
                else:
                    return HardwareProfile.POCKET
            # Truly no info at all
            logger.warning("No VRAM data available — defaulting to PORTABLE")
            return HardwareProfile.PORTABLE

        # Step 4: Map VRAM bytes to profile
        total_vram_gb = total_vram_bytes / (1024 ** 3)
        logger.info("Detected %.1f GB VRAM available", total_vram_gb)

        if total_vram_gb < 6:
            return HardwareProfile.POCKET
        elif total_vram_gb < 12:
            return HardwareProfile.PORTABLE
        elif total_vram_gb < 23:
            return HardwareProfile.STANDARD
        else:
            return HardwareProfile.POWER

    except ConnectionError:
        logger.warning(
            "Ollama not reachable at %s — defaulting to PORTABLE",
            ollama_host,
        )
        return HardwareProfile.PORTABLE
    except Exception as exc:
        logger.warning(
            "Unexpected error during profile detection: %s — defaulting to PORTABLE",
            exc,
        )
        return HardwareProfile.PORTABLE
```

**What this does:**
1. Tries to read VRAM info from `/api/ps` (running models).
2. If nothing is running, loads `qwen3:0.6b` as a probe, checks VRAM, unloads.
3. If VRAM data is still unavailable, falls back to model file size heuristics.
4. Maps total VRAM to the four hardware profiles using the thresholds from SRS Section 2.2.
5. If Ollama is not reachable at all, returns `PORTABLE` as a safe default.

---

## Phase 3: Adaptive Model Manager

### Step 3.1: Add the AdaptiveModelManager class

Append the following class to the **bottom** of `gwen/core/model_manager.py`:

```python
# ---------------------------------------------------------------------------
# AdaptiveModelManager
# ---------------------------------------------------------------------------

class AdaptiveModelManager:
    """Maps logical tiers (0, 1, 2) to physical Ollama models.

    The orchestrator never knows which physical model it's talking to.
    It requests a tier, and this class provides the appropriate model
    based on the detected hardware profile.

    Usage
    -----
    >>> profile = await detect_profile()
    >>> mgr = AdaptiveModelManager(profile)
    >>> await mgr.ensure_tier_loaded(0)
    >>> response = await mgr.generate(tier=0, prompt="Classify this message")
    """

    # Maps each HardwareProfile to {logical_tier: physical_model_name}.
    # These MUST match SRS.md Section 3.16 exactly.
    TIER_MAPS: dict[HardwareProfile, dict[int, str]] = {
        HardwareProfile.POCKET: {
            0: "qwen3:0.6b",
            1: "qwen3:0.6b",
            2: "qwen3:0.6b",
        },
        HardwareProfile.PORTABLE: {
            0: "qwen3:0.6b",
            1: "qwen3:8b-q3",
            2: "qwen3:8b-q3",
        },
        HardwareProfile.STANDARD: {
            0: "qwen3:0.6b",
            1: "qwen3:8b",
            2: "qwen3-coder:30b",
        },
        HardwareProfile.POWER: {
            0: "qwen3:0.6b",
            1: "qwen3:8b",
            2: "qwen3-coder:30b",
        },
    }

    # Concurrency constraints per profile.
    # max_concurrent: how many models can be in VRAM simultaneously.
    # tier2_strategy: how to handle Tier 2 loading.
    #   "inline"     — Tier 2 IS the same model (Pocket).
    #   "time_share" — Unload Tier 1 before loading Tier 2 (Portable/Standard).
    #   "concurrent" — All tiers loaded simultaneously (Power).
    CONCURRENCY: dict[HardwareProfile, dict[str, Any]] = {
        HardwareProfile.POCKET: {
            "max_concurrent": 1,
            "tier2_strategy": "inline",
        },
        HardwareProfile.PORTABLE: {
            "max_concurrent": 2,
            "tier2_strategy": "time_share",
        },
        HardwareProfile.STANDARD: {
            "max_concurrent": 2,
            "tier2_strategy": "time_share",
        },
        HardwareProfile.POWER: {
            "max_concurrent": 3,
            "tier2_strategy": "concurrent",
        },
    }

    # The embedding model is always the same regardless of profile.
    EMBEDDING_MODEL: str = "qwen3-embedding:0.6b"

    def __init__(
        self,
        profile: HardwareProfile,
        ollama_host: str = "http://localhost:11434",
    ) -> None:
        """Initialise the manager for a specific hardware profile.

        Parameters
        ----------
        profile : HardwareProfile
            The detected (or user-overridden) hardware profile.
        ollama_host : str
            Ollama base URL.
        """
        self.profile = profile
        self.ollama_host = ollama_host
        self.tier_map: dict[int, str] = self.TIER_MAPS[profile]
        self.concurrency: dict[str, Any] = self.CONCURRENCY[profile]
        self.client = OllamaClient(host=ollama_host)
        # Track which tiers are currently loaded to avoid redundant loads.
        self._loaded_tiers: set[int] = set()
        logger.info(
            "AdaptiveModelManager initialised: profile=%s, tier_map=%s",
            profile.value,
            self.tier_map,
        )

    def get_model_for_tier(self, tier: int) -> str:
        """Return the physical model name for a logical tier.

        Parameters
        ----------
        tier : int
            Logical tier (0, 1, or 2).

        Returns
        -------
        str
            Physical Ollama model name (e.g. ``"qwen3:0.6b"``).

        Raises
        ------
        ValueError
            If the tier is not 0, 1, or 2.
        """
        if tier not in self.tier_map:
            raise ValueError(
                f"Invalid tier {tier}. Must be 0, 1, or 2."
            )
        return self.tier_map[tier]

    async def ensure_tier_loaded(self, tier: int) -> None:
        """Load the model for a tier, respecting concurrency limits.

        This method implements the concurrency strategy from SRS.md
        Section 3.16:

        - **Pocket** (max_concurrent=1): Unload all other models before
          loading.  In practice, the same 0.6b model plays all roles,
          so this is usually a no-op.
        - **Portable / Standard** (max_concurrent=2, time_share): Tier 0
          and Tier 1 can coexist.  When Tier 2 is needed, Tier 1 is
          unloaded first to free VRAM.
        - **Power** (max_concurrent=3, concurrent): All tiers loaded
          simultaneously.

        Parameters
        ----------
        tier : int
            Logical tier (0, 1, or 2).
        """
        model = self.get_model_for_tier(tier)
        max_concurrent = self.concurrency["max_concurrent"]
        tier2_strategy = self.concurrency["tier2_strategy"]

        if max_concurrent == 1:
            # Pocket: unload everything else before loading
            await self._unload_all_except(model)
        elif tier == 2 and tier2_strategy == "time_share":
            # Portable / Standard: unload Tier 1 to make room for Tier 2
            tier1_model = self.get_model_for_tier(1)
            if 1 in self._loaded_tiers:
                await self.client.unload_model(tier1_model)
                self._loaded_tiers.discard(1)
                logger.info(
                    "Unloaded Tier 1 (%s) to make room for Tier 2 (%s)",
                    tier1_model, model,
                )
        # else: Power profile — just load, everything fits

        try:
            await self.client.load_model(model)
            self._loaded_tiers.add(tier)
        except ConnectionError as exc:
            logger.error("Failed to load tier %d (%s): %s", tier, model, exc)
            raise

    async def generate(
        self,
        tier: int,
        prompt: str,
        system: Optional[str] = None,
        format: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> str:
        """Generate a completion using the model mapped to a logical tier.

        This is the primary interface the orchestrator uses.  The
        orchestrator says ``generate(tier=1, prompt=...)`` and never
        needs to know that Tier 1 is ``qwen3:8b`` on Standard hardware
        but ``qwen3:0.6b`` on Pocket hardware.

        Parameters
        ----------
        tier : int
            Logical tier (0, 1, or 2).
        prompt : str
            The prompt to send to the model.
        system : str | None
            Optional system prompt.
        format : str | None
            Set to ``"json"`` for structured output.
        options : dict | None
            Model parameters (temperature, top_p, num_predict, etc.).

        Returns
        -------
        str
            The model's response text.

        Raises
        ------
        ConnectionError
            If Ollama is not reachable.
        """
        model = self.get_model_for_tier(tier)
        return await self.client.generate(
            model=model,
            prompt=prompt,
            system=system,
            format=format,
            options=options,
        )

    async def embed(self, text: str) -> list[float]:
        """Compute a semantic embedding for the given text.

        Always uses ``qwen3-embedding:0.6b`` regardless of hardware
        profile — the embedding model is small enough for any tier.

        Parameters
        ----------
        text : str
            Text to embed.

        Returns
        -------
        list[float]
            1024-dimensional embedding vector.
        """
        return await self.client.embed(
            model=self.EMBEDDING_MODEL,
            text=text,
        )

    # -- private helpers ----------------------------------------------------

    async def _unload_all_except(self, keep_model: str) -> None:
        """Unload all loaded models except ``keep_model``.

        Used by the Pocket profile where only one model fits in VRAM.

        Parameters
        ----------
        keep_model : str
            Model name to keep loaded.
        """
        try:
            running = await self.client.list_running()
        except ConnectionError:
            return

        for model_info in running:
            name = model_info.get("name", "")
            if name and name != keep_model:
                await self.client.unload_model(name)
                logger.info("Unloaded %s (keeping %s)", name, keep_model)

        # Reset tracking — only the kept model's tier is loaded
        self._loaded_tiers.clear()

    async def _unload_tier(self, tier: int) -> None:
        """Unload the model for a specific tier.

        Parameters
        ----------
        tier : int
            Logical tier whose model should be unloaded.
        """
        model = self.get_model_for_tier(tier)
        await self.client.unload_model(model)
        self._loaded_tiers.discard(tier)
```

**What this does:**
1. `TIER_MAPS` — copied exactly from SRS Section 3.16. Maps each HardwareProfile to its tier-to-model assignments.
2. `CONCURRENCY` — copied exactly from SRS Section 3.16. Controls how many models can be in VRAM.
3. `get_model_for_tier(tier)` — simple dict lookup, raises ValueError for invalid tiers.
4. `ensure_tier_loaded(tier)` — implements the three concurrency strategies: Pocket (unload everything), Portable/Standard (time-share Tier 2), Power (load all).
5. `generate(tier, prompt, ...)` — the main interface. Resolves tier to model, calls `OllamaClient.generate`.
6. `embed(text)` — always uses `qwen3-embedding:0.6b`.
7. `_unload_all_except` and `_unload_tier` — private helpers for VRAM management.

---

## Phase 4: Verification

### Step 4.1: Write tests/test_model_manager.py

Create the file `tests/test_model_manager.py` with the following exact content:

```python
"""Tests for gwen.core.model_manager — Ollama integration and adaptive profiles.

Run unit tests (no Ollama required):
    pytest tests/test_model_manager.py -v -k "not ollama"

Run ALL tests including Ollama integration:
    pytest tests/test_model_manager.py -v
"""

import asyncio
import json
import unittest.mock
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from gwen.core.model_manager import (
    AdaptiveModelManager,
    HardwareProfile,
    OllamaClient,
    detect_profile,
)


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

        import urllib.request as _ur
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
```

---

### Step 4.2: Run unit tests (no Ollama required)

Execute the following command from the project root:

```bash
pytest tests/test_model_manager.py -v -k "not ollama"
```

**Expected result:** All unit tests pass. The integration tests in `TestOllamaIntegration` are skipped because they are filtered by `-k "not ollama"`.

If you also want to run the integration tests (requires Ollama running with `qwen3:0.6b` and `qwen3-embedding:0.6b` pulled):

```bash
pytest tests/test_model_manager.py -v -m ollama
```

**Common failure causes:**
1. **ImportError for gwen.core.model_manager**: Track 001 (project scaffold) must be complete so `gwen` is importable.
2. **pytest-asyncio not installed**: Run `pip install pytest-asyncio`.
3. **Integration test failures**: Ollama must be running with the required models pulled.

---

## Checklist (update after each step)

- [x] Phase 1 complete: gwen/core/__init__.py and model_manager.py with OllamaClient
- [x] Phase 2 complete: detect_profile() function
- [x] Phase 3 complete: AdaptiveModelManager class with TIER_MAPS, CONCURRENCY, generate, embed, ensure_tier_loaded
- [x] Phase 4 complete: tests/test_model_manager.py passes (unit tests, no Ollama required)

**Implementation note:** Since Track 002 was already complete, `HardwareProfile` is imported from `gwen.models.classification` rather than redefined locally as the plan suggested. Tests import from `gwen.models.classification` as well. 17 unit tests pass; 76 total (full suite, no regressions).
