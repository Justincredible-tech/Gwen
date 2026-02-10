"""Shared test fixtures for the Gwen test suite.

This file is automatically loaded by pytest before running any tests.
Add fixtures here that are needed across multiple test files.
"""

import pytest


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
