# 🚀 skills-but-for-dev — Launch Distribution Pack
*Your complete, ready-to-copy launch blueprint to reach #1 on GitHub Trending and Repo of the Day.*

---

## ⏰ Launch Timing Strategy (The Golden Window)

* **Recommended Launch Day:** **Tuesday (or Wednesday)**
* **Target Launch Time:** **15:45 – 16:15 TSİ (08:45 – 09:15 AM EST / 05:45 – 06:15 AM PST)**
* **Why this exact window?**
  * Europe is in peak afternoon productivity.
  * US East Coast (New York, Boston) is opening laptops and checking morning Hacker News / Twitter / Reddit with coffee.
  * US West Coast (Silicon Valley) wakes up at 09:00 PST (19:00 TSİ) to sustain the trending velocity throughout the evening.
  * GitHub Trending calculates daily velocity on UTC 00:00 - 23:59. Launching at 16:00 TSİ accumulates 11 hours of peak global stars in the **same UTC day**, maximizing Trending rank.

---

## 1. 🟠 Hacker News (Show HN)

* **Submission URL:** `https://news.ycombinator.com/submit`
* **URL:** `https://github.com/MelihcanTheGreat/Skills-but-for-dev`

### Title Options (Choose one):
* **Option A (Recommended - Technical & Direct):**
  > `Show HN: Skills-but-for-dev – Real-time tech stack and repo curator for AI agents`
* **Option B (Problem-focused):**
  > `Show HN: Stop your AI agent from building code on abandoned 2022 libraries`
* **Option C (Data/Metric-focused):**
  > `Show HN: An MCP server that checks GitHub velocity and PyPI stats before coding`

---

### First Comment (Post immediately after submitting your Show HN):

```markdown
Hey HN,

I built skills-but-for-dev because I kept running into the same frustrating experience with Cursor, Claude Code, and Antigravity:

Whenever I asked an agent to build something non-trivial (e.g. "build a meeting assistant that records audio, separates speakers, and generates summaries"), the agent would immediately start generating code using whatever libraries were frozen in its training data cutoff.

This led to three recurring problems:
1. Recommending abandoned projects: Repos with 35k stars that haven't had a commit in 18 months.
2. Invisibility of breakout tools: The fastest voice model or RAG parser released last month doesn't exist in the LLM's weights.
3. Licensing & Hardware traps: Generating code importing GPL/NC packages for commercial projects, or recommending a 14B model that immediately OOM-crashes an 8GB VRAM developer card.

`skills-but-for-dev` is a lightweight FastMCP server that serves as a pre-flight tech stack curator for AI agents. Before your agent writes code, it calls the MCP server to inspect live open-source metrics:

- Dual-Bucket Search: Retrieves proven industry giants (`stars:>500`) alongside fast-rising breakout repos (`stars:75..3500`, pushed < 30 days) so newer libraries aren't cannibalized.
- Star Velocity & Acceleration: Computes 4-week moving average ($v_4$) and acceleration ratio ($v_4 / v_{12}$) from GitHub's star history.
- Real-World PyPI Adoption: Queries pypistats.org for monthly downloads to detect GitHub star inflation and bot manipulation.
- Hardware & VRAM Estimation: Computes actual memory ceilings across safetensors, sharded weights, Diffusers, and GGUF quantization levels (Q4_K_M, Q8_0).
- Anti-Prompt-Injection Sanitizer: Strips malicious zero-width tags and prompt-injection payloads from third-party READMEs before feeding context back to the LLM.
- Zero-config auth: Automatically discovers existing tokens from the GitHub CLI (`gh auth token`) or falls back gracefully to a quota-conserving unauthenticated mode.

It runs locally with zero installation via `uvx`:
```bash
uvx skills-but-for-dev ping
```

And integrates with Cursor, Claude Desktop, Antigravity, or Windsurf with 4 lines in your MCP configuration.

GitHub: https://github.com/MelihcanTheGreat/Skills-but-for-dev
PyPI: https://pypi.org/project/skills-but-for-dev/

I'd love to hear your feedback on our scoring formulas and what additional package registries (e.g., crates.io, npm) you'd like to see next!
```

---

## 2. 🔴 Reddit Strategy

### Subreddit 1: `r/cursor`
* **URL:** `https://www.reddit.com/r/cursor/submit`
* **Title:** `I got tired of Cursor writing code with abandoned 2022 libraries, so I built an MCP server that verifies GitHub star velocity and PyPI adoption before writing code`
* **Flair:** Project / Tool

**Body:**
```markdown
Hey everyone,

Whenever I ask Cursor to bootstrap a complex feature (like audio diarization, PDF table extraction, or local RAG), it almost always suggests whatever popular library was trending when its training data was frozen. 

Half the time, those 30k-star repos have had zero commits in 18 months, while a state-of-the-art C++/Rust-accelerated library released 3 months ago is completely ignored.

To fix this for my own workflow, I built an open-source MCP server called **skills-but-for-dev**.

### What it does:
Before Cursor writes code, it executes a live pre-flight check across GitHub, PyPI, and Hugging Face:
- **Dual-Bucket Discovery:** Finds established leaders AND fast-rising breakout repositories (`stars:75..3500`, pushed < 30 days).
- **PyPI Monthly Adoption:** Checks real monthly download counts on `pypistats.org` to verify if developers actually use it in production (guards against GitHub star inflation).
- **Star Velocity:** Measures weekly star momentum and acceleration ratio ($v_4 / v_{12}$).
- **License Compliance:** Automatically flags and penalizes GPL-3.0 or non-commercial licenses if you specify commercial safety.
- **Hardware Check:** Estimates minimum VRAM requirements for Hugging Face models & GGUF quant levels before Cursor writes code that OOMs your GPU.

### How to use it in Cursor:
Add this to your `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "skills-but-for-dev": {
      "command": "uvx",
      "args": ["skills-but-for-dev"]
    }
  }
}
```

It automatically detects your GitHub CLI login (`gh auth token`) if you have it installed, so no API keys or token setup is required.

Repo: https://github.com/MelihcanTheGreat/Skills-but-for-dev  
PyPI: https://pypi.org/project/skills-but-for-dev/

Would love to know what package ecosystems you think would be most useful to add next!
```

---

### Subreddit 2: `r/LocalLLaMA`
* **URL:** `https://www.reddit.com/r/LocalLLaMA/submit`
* **Title:** `Built a local MCP tool for AI agents that estimates real VRAM requirements (GGUF quants / safetensors) and flags dormant repo spikes`
* **Flair:** Tool / Software

**Body:**
```markdown
Hey r/LocalLLaMA,

When using coding agents (Claude, Cursor, Antigravity) to build local AI pipelines, one major pain point is agents recommending models that blow through your available VRAM or suggesting dormant models whose weights haven't been updated in years.

I open-sourced **skills-but-for-dev**, an MCP server designed to be called by agents before they recommend models or open-source repositories.

### What it provides for local workflows:
1. **Accurate VRAM Estimation:** Automatically inspects `.safetensors`, sharded index headers, and GGUF quant levels (`Q4_K_M`, `Q8_0`, etc.) to provide agents with a realistic minimum VRAM ceiling (including 20% activation overhead).
2. **Dormant Spike Detection:** Detects suspicious repositories that sat inactive for 6+ months and suddenly gained thousands of stars in a single week.
3. **Dual-Bucket Search:** Recommends breakout new libraries alongside battle-tested foundations.
4. **Sub-5ms SQLite WAL Cache:** All requests are cached locally so repeated agent queries don't hit rate limits or slow down generation.

Runs with `uvx skills-but-for-dev` with zero installation.

GitHub: https://github.com/MelihcanTheGreat/Skills-but-for-dev  
PyPI: https://pypi.org/project/skills-but-for-dev/

Feedback and suggestions on quant estimation formulas are very welcome!
```

---

### Subreddit 3: `r/Python`
* **URL:** `https://www.reddit.com/r/Python/submit`
* **Title:** `skills-but-for-dev: An open-source MCP server to protect AI coding agents from dead repos and star inflation`
* **Flair:** Project

**Body:**
```markdown
Hey everyone,

I built **skills-but-for-dev**, an asynchronous Python package and Model Context Protocol (FastMCP) server that helps AI agents discover healthy, active, and license-compliant technology stacks.

### What problem does it solve?
LLMs are frozen in time. When asked to architect a stack, they default to high-star projects that are frequently abandoned or unmaintained. At the same time, GitHub stars can be heavily inflated.

`skills-but-for-dev` combines:
1. Real-time GitHub search with multi-level query relaxation
2. Star velocity and momentum calculations ($v_4$ and $v_{12}$ moving averages)
3. 30-day download counts from PyPI (`pypistats.org`)
4. License classification (permissive vs. weak/strong copyleft vs. non-commercial)
5. A lightweight async SQLite caching layer in WAL mode (average warm response latency: ~4.7ms)

Zero config is needed—it auto-discovers your GitHub CLI token (`gh auth token`) or falls back to an adaptive unauthenticated mode.

Tested with 40 unit tests across Python 3.11 and 3.12 with 100% pass rate.

- GitHub: https://github.com/MelihcanTheGreat/Skills-but-for-dev
- PyPI: https://pypi.org/project/skills-but-for-dev/

Check it out with: `uvx skills-but-for-dev ping`
```

---

## 3. 🌐 Awesome MCP Lists & Registries

### A. Pull Request for `punkpeye/awesome-mcp-servers`
* **Target Repo:** `https://github.com/punkpeye/awesome-mcp-servers`
* **Target Section:** `Development / Code Analysis` or `Search`
* **Markdown Line to Add:**
```markdown
- [skills-but-for-dev](https://github.com/MelihcanTheGreat/Skills-but-for-dev) 🐍 - Intelligent technology stack and open-source repo curator for AI agents with real-time star velocity, PyPI adoption, and license verification.
```
* **PR Title:** `Add skills-but-for-dev to Developer Tools`
* **PR Description:**
```markdown
### Name
`skills-but-for-dev`

### Description
An open-source FastMCP server that enables AI coding agents (Cursor, Claude Code, Antigravity) to evaluate live GitHub velocity, PyPI monthly adoption, Hugging Face VRAM baselines, and license compliance before generating code.

### Links
- Repo: https://github.com/MelihcanTheGreat/Skills-but-for-dev
- PyPI: https://pypi.org/project/skills-but-for-dev/
- License: Apache-2.0
```

---

### B. Registry Submissions

1. **Smithery.ai:**
   Run from your terminal:
   ```bash
   npx -y @smithery/cli@latest publish
   ```
2. **Glama.ai (`mcp.so`):**
   Navigate to [https://glama.ai/mcp/servers](https://glama.ai/mcp/servers) and click **"Submit a Server"**.
   - Name: `skills-but-for-dev`
   - Repository: `https://github.com/MelihcanTheGreat/Skills-but-for-dev`
   - Command: `uvx skills-but-for-dev`

---

## 4. 🐦 X / Twitter Thread Template

**Tweet 1 (Hook):**
> Your AI coding agent (Cursor, Claude, Copilot) is building production code on abandoned 2022 libraries.
> 
> High GitHub stars don't mean a repo is alive.
> 
> I built skills-but-for-dev: an open-source MCP server that gives your agent live star velocity, PyPI stats, and VRAM checks before writing code. 🧵👇

**Tweet 2 (The Problem):**
> Why does this happen?
> 
> LLMs rely on static pre-training data.
> - A repo with 35k stars might have 0 commits in 18 months.
> - Fast-rising breakout libraries released last month are invisible.
> - Hidden GPL-3.0 licenses create commercial liabilities.

**Tweet 3 (The Solution):**
> skills-but-for-dev checks live metrics in real-time:
> ⚡ Dual-bucket search: balances giants (`stars:>500`) with breakout newcomers
> 📈 PyPI monthly downloads: protects against star inflation
> 💻 VRAM estimator: checks GPU memory before crashing your machine
> 🛡️ Anti-prompt injection sanitizer

**Tweet 4 (Zero Installation):**
> Zero setup needed. Works with Cursor, Claude Desktop, Antigravity, or Windsurf:
> 
> ```json
> {
>   "mcpServers": {
>     "skills-but-for-dev": {
>       "command": "uvx",
>       "args": ["skills-but-for-dev"]
>     }
>   }
> }
> ```
> Auto-detects your `gh auth token` automatically.

**Tweet 5 (Link & Call to Action):**
> 100% open source (Apache 2.0). 40/40 tests passing. Sub-5ms SQLite WAL cache.
> 
> ⭐ Star the repo and try it on your next project:
> https://github.com/MelihcanTheGreat/Skills-but-for-dev
> 
> PyPI: https://pypi.org/project/skills-but-for-dev/
