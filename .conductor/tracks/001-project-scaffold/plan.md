# Plan: Project Scaffold

**Track:** 001-project-scaffold
**Spec:** [spec.md](./spec.md)
**Status:** Complete

---

## Phase 1: Project Configuration

### Step 1.1: Create pyproject.toml

Create the file `pyproject.toml` in the project root (`C:\Users\Administrator\Desktop\projects\Gwen\pyproject.toml`).

- [x] Write pyproject.toml with all metadata and dependencies (Done: `pyproject.toml`)

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gwen"
version = "0.1.0"
description = "Open-source framework for building persistent, emotionally intelligent AI companions on local hardware."
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [
    {name = "Gwen Contributors"}
]

dependencies = [
    "pydantic>=2.0",
    "chromadb>=0.4.0",
    "networkx>=3.0",
    "cryptography>=41.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]

[tool.setuptools.packages.find]
include = ["gwen*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "ollama: marks tests that require a running Ollama instance (deselect with '-m \"not ollama\"')",
]
```

**Why these choices:**
- `setuptools` is the most widely supported build backend and works on all platforms.
- Dependencies are split: runtime deps in `dependencies`, testing deps in `[project.optional-dependencies] dev`. This lets users install without test tools.
- `asyncio_mode = "auto"` means pytest-asyncio will automatically handle async test functions without needing `@pytest.mark.asyncio` on every test.
- The `ollama` marker lets us skip integration tests in CI where no Ollama server is running.

---

### Step 1.2: Create gwen/__init__.py

Create the file `gwen/__init__.py` (relative to project root: `C:\Users\Administrator\Desktop\projects\Gwen\gwen\__init__.py`).

- [x] Write gwen/__init__.py with version string (Done: `gwen/__init__.py`)

```python
"""Gwen - Open-source AI companion framework."""

__version__ = "0.1.0"
```

**What this does:** Makes `gwen` a Python package. The `__version__` variable is the single source of truth for the project version. It matches the version in pyproject.toml. Later code can do `from gwen import __version__` to get the version at runtime.

---

## Phase 2: Package Structure

### Step 2.1: Create all subdirectory __init__.py files

Create one `__init__.py` file inside each subdirectory of `gwen/`. Every file below has the same content pattern: a one-line docstring describing the subpackage.

- [x] Create all 12 subpackage __init__.py files (Done: `gwen/*/\__init__.py`)

**File: `gwen/models/__init__.py`**
```python
"""Data models, enums, and Pydantic schemas for the Gwen system."""
```

**File: `gwen/core/__init__.py`**
```python
"""Core orchestrator and service layer."""
```

**File: `gwen/classification/__init__.py`**
```python
"""Tier 0 classification pipeline and rule engine."""
```

**File: `gwen/memory/__init__.py`**
```python
"""Five-tier Living Memory system."""
```

**File: `gwen/temporal/__init__.py`**
```python
"""Temporal Cognition System - TME generation, circadian analysis, gap detection."""
```

**File: `gwen/amygdala/__init__.py`**
```python
"""Amygdala Layer - emotional modulation of storage, retrieval, and decay."""
```

**File: `gwen/safety/__init__.py`**
```python
"""Safety Architecture - threat detection, encrypted ledger, wellness checks."""
```

**File: `gwen/compass/__init__.py`**
```python
"""Compass Framework - four-direction life coaching integration."""
```

**File: `gwen/autonomy/__init__.py`**
```python
"""Autonomy Engine - proactive contact triggers and decision model."""
```

**File: `gwen/consolidation/__init__.py`**
```python
"""Background memory consolidation - light, standard, and deep passes."""
```

**File: `gwen/personality/__init__.py`**
```python
"""Personality module system - YAML loading and dynamic prompt injection."""
```

**File: `gwen/ui/__init__.py`**
```python
"""User interface layer - CLI (Phase 1), GUI (future)."""
```

**How to create these:** For each file path above, create the directory if it does not exist, then write the file with the exact content shown. The directory structure after this step should be:

```
gwen/
  __init__.py          (from Step 1.2)
  models/__init__.py
  core/__init__.py
  classification/__init__.py
  memory/__init__.py
  temporal/__init__.py
  amygdala/__init__.py
  safety/__init__.py
  compass/__init__.py
  autonomy/__init__.py
  consolidation/__init__.py
  personality/__init__.py
  ui/__init__.py
```

---

### Step 2.2: Create tests directory with __init__.py and conftest.py

Create two files inside the `tests/` directory at the project root.

- [x] Create tests/__init__.py (Done: `tests/__init__.py`)
- [x] Create tests/conftest.py with fixture placeholders (Done: `tests/conftest.py`)

**File: `tests/__init__.py`**
```python
"""Gwen test suite."""
```

**File: `tests/conftest.py`**
```python
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
```

**Why these fixtures:** The data models track (002) will need consistent test values for the EmotionalStateVector. By defining them here, every test file can use them without duplication. More fixtures will be added as tracks are implemented.

---

### Step 2.3: Create data/personalities/.gitkeep

Create the directory `data/personalities/` at the project root, with a `.gitkeep` file so git tracks the empty directory.

- [x] Create data/personalities/.gitkeep (Done: `data/personalities/.gitkeep`)

**File: `data/personalities/.gitkeep`**
```
```

(The file is intentionally empty. Its only purpose is to make git track the `data/personalities/` directory.)

---

## Phase 3: Verification

### Step 3.1: Install the package in editable mode

Run this command from the project root directory (`C:\Users\Administrator\Desktop\projects\Gwen\`):

- [x] Run `pip install -e ".[dev]"` and confirm exit code 0 (Done: Successfully installed gwen-0.1.0)

```bash
pip install -e ".[dev]"
```

**Expected output:** The command prints installation progress and ends with `Successfully installed gwen-0.1.0` (or similar). The exit code is 0.

**If it fails:**
- If it says "pyproject.toml not found", you are not in the project root. `cd` to `C:\Users\Administrator\Desktop\projects\Gwen\` and try again.
- If it says a dependency cannot be found, check that your pip is up to date: `pip install --upgrade pip`.
- If `setuptools` errors occur, make sure `setuptools>=68.0` is installed: `pip install --upgrade setuptools`.

---

### Step 3.2: Verify the package is importable

Run this command from any directory:

- [x] Run `python -c "import gwen; print(gwen.__version__)"` and confirm it prints "0.1.0" (Done: prints 0.1.0)

```bash
python -c "import gwen; print(gwen.__version__)"
```

**Expected output:**
```
0.1.0
```

**If it fails:**
- If it says `ModuleNotFoundError: No module named 'gwen'`, the editable install did not work. Re-run Step 3.1.
- If it prints a different version, check that `gwen/__init__.py` has `__version__ = "0.1.0"` and that no other `gwen` package is installed (run `pip show gwen` to check the install location).

---

### Step 3.3: Verify pytest can discover the test directory

Run this command from the project root:

- [x] Run `pytest tests/ --co` and confirm it finds conftest.py (Done: exit code 5, no tests collected — expected)

```bash
pytest tests/ --co
```

**Expected output:** pytest starts up, shows the test session header, and lists `tests/conftest.py` as a collected item (or "no tests ran" since there are no test functions yet, but it should NOT error). The exit code should be 0 or 5 (5 means "no tests collected", which is expected at this stage).

**If it fails:**
- If pytest is not found, re-run `pip install -e ".[dev]"` from Step 3.1.
- If it errors on import, check that `tests/__init__.py` exists.

---

## Summary of Files Created

| Step | File Path | Purpose |
|------|-----------|---------|
| 1.1 | `pyproject.toml` | Project metadata, dependencies, build config |
| 1.2 | `gwen/__init__.py` | Root package with version |
| 2.1 | `gwen/models/__init__.py` | Models subpackage |
| 2.1 | `gwen/core/__init__.py` | Core subpackage |
| 2.1 | `gwen/classification/__init__.py` | Classification subpackage |
| 2.1 | `gwen/memory/__init__.py` | Memory subpackage |
| 2.1 | `gwen/temporal/__init__.py` | Temporal subpackage |
| 2.1 | `gwen/amygdala/__init__.py` | Amygdala subpackage |
| 2.1 | `gwen/safety/__init__.py` | Safety subpackage |
| 2.1 | `gwen/compass/__init__.py` | Compass subpackage |
| 2.1 | `gwen/autonomy/__init__.py` | Autonomy subpackage |
| 2.1 | `gwen/consolidation/__init__.py` | Consolidation subpackage |
| 2.1 | `gwen/personality/__init__.py` | Personality subpackage |
| 2.1 | `gwen/ui/__init__.py` | UI subpackage |
| 2.2 | `tests/__init__.py` | Test package |
| 2.2 | `tests/conftest.py` | Shared test fixtures |
| 2.3 | `data/personalities/.gitkeep` | Placeholder for personality YAML files |

**Total files:** 17
**Total directories created:** 15 (gwen/ + 12 subpackages + tests/ + data/personalities/)
