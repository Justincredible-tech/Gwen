"""Shared test fixtures for the Gwen test suite.

This file is automatically loaded by pytest before running any tests.
Add fixtures here that are needed across multiple test files.
"""

import tempfile

import pytest

from gwen.core.model_manager import OllamaClient


# ---------------------------------------------------------------------------
# Live integration fixtures (session-scoped to avoid cold starts)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ollama_client():
    """Session-scoped OllamaClient for live integration tests."""
    return OllamaClient()


@pytest.fixture(scope="session")
def ollama_available(ollama_client):
    """Check if Ollama is reachable. Skip tests if not."""
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(ollama_client.list_models())
        loop.close()
        return True
    except Exception:
        pytest.skip("Ollama not available")


@pytest.fixture(scope="session")
def live_model_manager(ollama_available):
    """Session-scoped AdaptiveModelManager with real profile detection."""
    import asyncio
    from gwen.core.model_manager import AdaptiveModelManager, detect_profile

    loop = asyncio.new_event_loop()
    profile = loop.run_until_complete(detect_profile())
    mgr = AdaptiveModelManager(profile)
    loop.run_until_complete(mgr.ensure_tier_loaded(0))
    loop.run_until_complete(mgr.ensure_tier_loaded(1))
    loop.close()
    return mgr


@pytest.fixture(scope="session")
def live_tier0(live_model_manager):
    """Session-scoped Tier0Classifier with real model."""
    from gwen.classification.tier0 import Tier0Classifier
    return Tier0Classifier(model_manager=live_model_manager)


@pytest.fixture
def temp_data_dir():
    """Function-scoped temporary data directory for test isolation."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        yield tmpdir


@pytest.fixture
def live_embedding_service(ollama_available):
    """Function-scoped EmbeddingService with ephemeral ChromaDB."""
    import chromadb
    from gwen.memory.embeddings import EmbeddingService
    client = chromadb.Client()
    return EmbeddingService(chromadb_client=client)


@pytest.fixture
def sample_valence() -> float:
    """A sample valence value for testing emotional models."""
    return 0.65


@pytest.fixture
def sample_arousal() -> float:
    """A sample arousal value for testing emotional models."""
    return 0.45


@pytest.fixture
def sample_dominance() -> float:
    """A sample dominance value for testing."""
    return 0.50


@pytest.fixture
def sample_relational_significance() -> float:
    """A sample relational significance value for testing."""
    return 0.70


@pytest.fixture
def sample_vulnerability_level() -> float:
    """A sample vulnerability level value for testing."""
    return 0.30
