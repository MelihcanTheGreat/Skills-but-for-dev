# Contributing to skills-but-for-dev

Thank you for your interest in contributing to `skills-but-for-dev`! We welcome contributions of all kinds: bug reports, documentation enhancements, additional query normalization rules, license classifications, and new benchmark scenarios.

---

## 🛠️ Development Setup

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Local Environment Setup

```bash
# Clone the repository
git clone https://github.com/MelihcanTheGreat/Skills-but-for-dev.git
cd Skills-but-for-dev

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install package in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## 🧪 Testing and Code Quality

We maintain a strict zero-regression standard:

```bash
# Run the complete unit test suite
python -m pytest -v

# Run the linter and code quality checks (Ruff)
python -m ruff check .

# Automatically fix minor formatting/import issues
python -m ruff check --fix .
```

All 40+ unit tests must pass, and `ruff check .` must report zero errors before opening a Pull Request.

---

## 📊 Running Evaluation Benchmarks

To verify candidate ranking quality and cache speedups:

```bash
python evals/run_evals.py
```

This runs against realistic multi-layer agent scenarios defined in [`evals/queries.yaml`](evals/queries.yaml).

---

## 🌿 Pull Request Guidelines

1. **Create a Feature Branch:** Never work directly on `main`. Create a descriptive branch (e.g., `feat/rust-normalizer-rules` or `fix/pypi-alias-regex`).
2. **Add Unit Tests:** Any new logic or query normalization rules must include corresponding unit tests under [`tests/`](tests/).
3. **Commit Convention:** Use Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`).
4. **Documentation:** If modifying MCP tool signatures or configuration settings, update both [`README.md`](README.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 📄 License

By contributing to `skills-but-for-dev`, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
