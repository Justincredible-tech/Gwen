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
from typing import Any, Optional

from gwen.models.classification import HardwareProfile

logger = logging.getLogger(__name__)


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
            1: "qwen3-coder:30b",
            2: "qwen3-coder:30b",
        },
        HardwareProfile.POWER: {
            0: "qwen3:0.6b",
            1: "qwen3-coder:30b",
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

    async def swap_tier1_variant(self, variant: str) -> None:
        """Swap the Tier 1 model to a different variant.

        Used by the Mode System to switch between standard and uncensored
        Tier 1 models when entering/exiting Immersion Mode.

        Parameters
        ----------
        variant : str
            The variant name (e.g. ``"standard"`` or ``"uncensored"``).

        Notes
        -----
        This is currently a placeholder. In production, this would unload
        the current Tier 1 model and load the appropriate variant. The
        actual uncensored model names will be configured per profile once
        available in Ollama.
        """
        logger.info("Tier 1 variant swap requested: %s (placeholder)", variant)

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
