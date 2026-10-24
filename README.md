# stack-scout

> **Intelligent technology stack and open-source curator for AI agents (Cursor, Antigravity, and MCP-compatible environments).**

`stack-scout` is a Model Context Protocol (MCP) server and agent skill that recommends **fresh, healthy, and license-compliant** GitHub repositories and Hugging Face models/Spaces before you start writing code.

---

## ⚡ The Problem: Knowledge Cutoff & Dead Repositories

When coding assistants (Cursor, Antigravity, Claude Code) are asked to *"Build an AI meeting assistant that takes notes"*, they often generate code from 2-year-old libraries stored in their training data. Meanwhile:
- Outdated repos with 30,000 stars might be completely abandoned.
- State-of-the-art voice and speech models released last week on Hugging Face remain invisible.
- High-star repos with non-commercial (CC-BY-NC) or strong copyleft (GPL) licenses create legal hazards for startups.

`stack-scout` eliminates this blind spot.

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

### 2. Configure in Antigravity or Cursor

#### Antigravity (`mcp_config.json`)
```json
{
  "mcpServers": {
    "stack-scout": {
      "command": "python",
      "args": ["-m", "stack_scout.server"],
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
    "stack-scout": {
      "command": "python",
      "args": ["-m", "stack_scout.server"],
      "env": {
        "GITHUB_TOKEN": "your_github_pat_here"
      }
    }
  }
}
```

---

## 📖 Architecture & Design

See [ARCHITECTURE.md](ARCHITECTURE.md) for full architectural specifications, mathematical formulas, and rate-limit budgets.

---

## 📄 License

Apache-2.0
