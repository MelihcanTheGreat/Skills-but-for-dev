# skills-but-for-dev

[![PyPI](https://img.shields.io/pypi/v/skills-but-for-dev.svg)](https://pypi.org/project/skills-but-for-dev/)
[![CI](https://github.com/MelihcanTheGreat/Skills-but-for-dev/actions/workflows/ci.yml/badge.svg)](https://github.com/MelihcanTheGreat/Skills-but-for-dev/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

> **Intelligent technology stack and open-source curator for AI agents (Cursor, Antigravity, and MCP-compatible environments).**

`skills-but-for-dev` is a Model Context Protocol (MCP) server and agent skill that recommends **fresh, healthy, and license-compliant** GitHub repositories and Hugging Face models/Spaces before you start writing code.

---

## ⚡ The Problem: Knowledge Cutoff & Dead Repositories

When coding assistants (Cursor, Antigravity, Claude Code) are asked to *"Build an AI meeting assistant that takes notes"*, they often generate code from 2-year-old libraries stored in their training data. Meanwhile:
- Outdated repos with 30,000 stars might be completely abandoned.
- State-of-the-art voice and speech models released last week on Hugging Face remain invisible.
- High-star repos with non-commercial (CC-BY-NC) or strong copyleft (GPL) licenses create legal hazards for startups.

`skills-but-for-dev` eliminates this blind spot.

---

## 🛠️ Features

- **Dual-Bucket Search:** Catches established leaders (`stars:>500`) alongside rising breakout projects (`stars:75..3500`, pushed within 30 days) without cannibalization.
- **Real-Time Star Velocity:** Computes 4-week moving average and acceleration (`v4 / v12`) using the official GitHub star history API in a single request.
- **Smart VRAM Estimator:** Accurate minimum VRAM baseline calculation across `.safetensors`, sharded model files, diffusers components, and distinct GGUF quantizations (`Q4_K_M`, `Q8_0`).
- **Safety & Anti-Injection Sanitization:** Strips HTML comments, hidden zero-width tags, and giant YAML frontmatter blocks before injecting curated context into your IDE.
- **Zero LLM Overhead:** The MCP server is 100% deterministic, free, and runs locally with an asynchronous SQLite WAL cache. Reasoning and query decomposition are performed natively by your IDE model via `SKILL.md`.

---

## 🚀 Quickstart

### 1. Requirements
- Python 3.11+
- (Optional but recommended) `GITHUB_TOKEN` for higher GitHub API rate limits.

### 2. Run with Zero Installation (`uvx`)

You can launch `skills-but-for-dev` directly in any MCP-compatible environment without cloning or managing virtual environments:

```json
{
  "mcpServers": {
    "skills-but-for-dev": {
      "command": "uvx",
      "args": ["skills-but-for-dev"],
      "env": {
        "GITHUB_TOKEN": "your_github_pat_here"
      }
    }
  }
}
```

### 3. Configure in Antigravity or Cursor (Local Development)

#### Antigravity (`mcp_config.json`)
```json
{
  "mcpServers": {
    "skills-but-for-dev": {
      "command": "python",
      "args": ["-m", "skills_but_for_dev.server"],
      "env": {
        "GITHUB_TOKEN": "your_github_pat_here"
      }
    }
  }
}
```

#### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "skills-but-for-dev": {
      "command": "python",
      "args": ["-m", "skills_but_for_dev.server"],
      "env": {
        "GITHUB_TOKEN": "your_github_pat_here"
      }
    }
  }
}
```

### 4. CLI Diagnostics

You can inspect server health, token configuration, and cache paths directly from the terminal:

```bash
# Check version
skills-but-for-dev --version

# Ping and inspect active token/cache status
skills-but-for-dev ping
```

---

## 📖 Architecture & Design

See [ARCHITECTURE.md](ARCHITECTURE.md) for full architectural specifications, mathematical formulas, and rate-limit budgets.

---

## 📄 License

Apache-2.0

