# Spec: Project Scaffold

## 1. Context & Goal
Set up the Python project structure, package configuration, and all dependencies so that `pip install -e .` works and the `gwen` package is importable. This is the foundation everything else builds on.

## 2. Technical Approach
- Python 3.11+ project using pyproject.toml (modern packaging)
- All dependencies from tech-stack.md
- Directory structure from workflow.md
- pytest for testing

## 3. Requirements
- [ ] pyproject.toml with all dependencies and metadata
- [ ] gwen/ package directory with __init__.py
- [ ] All subdirectory packages created (models/, core/, classification/, memory/, temporal/, amygdala/, safety/, compass/, autonomy/, consolidation/, personality/, ui/)
- [ ] tests/ directory with conftest.py
- [ ] data/personalities/ directory
- [ ] `pip install -e .` succeeds
- [ ] `python -c "import gwen"` succeeds

## 4. Verification Plan
- [ ] `pip install -e .` exits with code 0
- [ ] `python -c "import gwen; print(gwen.__version__)"` prints "0.1.0"
- [ ] `pytest tests/ --co` (collect-only) finds conftest.py
