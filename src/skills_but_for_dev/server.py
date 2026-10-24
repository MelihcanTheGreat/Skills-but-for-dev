"""FastMCP Server entry point for skills-but-for-dev."""

from fastmcp import FastMCP

from skills_but_for_dev import __version__
from skills_but_for_dev.config import config

mcp = FastMCP("skills-but-for-dev")


@mcp.tool()
async def ping() -> str:
    """Check if the skills-but-for-dev MCP server is operational and view version & token status."""
    if config.token_source == "env":
        gh_status = "authenticated (source: environment variable)"
    elif config.token_source == "gh_cli":
        gh_status = "authenticated (source: GitHub CLI 'gh auth token')"
    else:
        gh_status = (
            "unauthenticated (60 req/hr limit). "
            "Tip: run 'gh auth login' or export GITHUB_TOKEN to unlock 5,000 req/hr."
        )

    hf_status = "configured" if config.hf_token else "unauthenticated"
    return (
        f"skills-but-for-dev v{__version__} is active.\n"
        f"- GitHub Token: {gh_status}\n"
        f"- Hugging Face Token: {hf_status}\n"
        f"- Cache Directory: {config.cache_dir}"
    )


@mcp.tool()
async def search_github_repos(
    query: str,
    topics: list[str] = [],
    language: str | None = None,
    commercial_use: bool = False,
    limit: int = 8,
) -> list[dict]:
    """Search for fresh, healthy, and license-compliant GitHub repositories for an architecture stack layer.

    When to use:
    - Before writing code for any project layer (e.g., 'speaker diarization', 'meeting bot').
    - To discover both proven industry leaders and fast-rising breakout repositories.

    Args:
        query: 2-3 English search keywords (e.g., 'speaker diarization', 'audio recorder').
        topics: Optional GitHub topic tags to refine results (e.g., ['diarization', 'webrtc']).
        language: Optional programming language filter (e.g., 'python', 'typescript').
        commercial_use: Set True if the user wants commercial viability (applies GPL/NC penalties).
        limit: Maximum number of ranked candidates to return (default: 8).

    Returns:
        List of candidate repositories with real-time star velocity, acceleration factor,
        license classification, anomaly warnings, and two-stage rankings.
    """
    from skills_but_for_dev.github_client import github_client

    candidates = await github_client.search_repositories(
        query=query,
        topics=topics,
        language=language,
        commercial_use=commercial_use,
        limit=limit,
    )
    if not candidates:
        from skills_but_for_dev.ratelimit import rate_limiter
        if rate_limiter.last_search_error:
            return [{"error": rate_limiter.last_search_error, "query": query}]
    return [c.model_dump() for c in candidates]


@mcp.tool()
async def get_repo_health(full_name: str) -> dict:
    """Fetch in-depth maintenance and responsiveness health metrics for a specific GitHub repository.

    Args:
        full_name: 'owner/repo' format (e.g., 'pyannote/pyannote-audio').

    Returns:
        Maintenance responsiveness score (0.0 - 1.0) based on releases, contributor breadth,
        and issue resolution speed.
    """
    from skills_but_for_dev.github_client import github_client

    parts = full_name.split("/")
    if len(parts) != 2:
        return {"error": "Invalid format, expected 'owner/repo'"}
    owner, repo = parts
    score = await github_client.get_repo_health(owner, repo)
    return {"full_name": full_name, "maintenance_score": score}


@mcp.tool()
async def search_hf_models(
    query: str,
    task: str | None = None,
    max_vram_gb: float | None = None,
    commercial_use: bool = False,
    limit: int = 8,
) -> list[dict]:
    """Search for open-source AI models on Hugging Face Hub with hardware/VRAM requirements.

    When to use:
    - Looking for ML/AI models for a specific task (e.g. 'automatic-speech-recognition', 'text-to-speech').
    - User has a local GPU limit (e.g. max_vram_gb=12.0) or needs commercial licensing.

    Args:
        query: Model keyword (e.g., 'whisper', 'diarization', 'qwen').
        task: Optional pipeline_tag (e.g., 'automatic-speech-recognition', 'voice-activity-detection').
        max_vram_gb: Hardware ceiling in GB. Models exceeding this memory baseline are filtered out.
        commercial_use: True applies penalties for CC-BY-NC or custom restrictive licenses.
        limit: Max candidates to return (default: 8).
    """
    from skills_but_for_dev.hf_client import hf_client

    candidates = await hf_client.search_models(
        query=query,
        task=task,
        max_vram_gb=max_vram_gb,
        commercial_use=commercial_use,
        limit=limit,
    )
    return [c.model_dump() for c in candidates]


@mcp.tool()
async def search_hf_spaces(query: str, limit: int = 5) -> list[dict]:
    """Search Hugging Face Spaces for running web demos, reference architectures, or prototypes.

    When to use:
    - User wants to see an interactive working demonstration of a model/framework in action.
    """
    from skills_but_for_dev.hf_client import hf_client

    spaces = await hf_client.search_spaces(query=query, limit=limit)
    return [s.model_dump() for s in spaces]


@mcp.tool()
async def get_readme(
    source: str,
    id: str,
    max_chars: int = 8000,
) -> str:
    """Fetch and sanitize documentation for a GitHub repo or Hugging Face model/Space.

    IMPORTANT SAFETY: Output is sanitized against prompt injection and wrapped in <untrusted_content> tags.
    Giant benchmark tables and YAML frontmatter blocks are omitted to prioritize Usage and Quickstart sections.

    Args:
        source: One of 'github', 'hf_model', or 'hf_space'.
        id: Identifier ('owner/repo' for GitHub, 'org/model-name' for Hugging Face).
        max_chars: Maximum characters to return (default: 8000).
    """
    import httpx

    from skills_but_for_dev.cache import cache, make_cache_key
    from skills_but_for_dev.config import config
    from skills_but_for_dev.sanitize import sanitize_readme

    cache_key = make_cache_key("readme_doc", source=source, id=id)
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    raw_text = ""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            if source == "github":
                # 1. Try raw CDN first (avoids consuming GitHub API Core rate limits)
                cdn_urls = [
                    f"https://raw.githubusercontent.com/{id}/HEAD/README.md",
                    f"https://raw.githubusercontent.com/{id}/main/README.md",
                    f"https://raw.githubusercontent.com/{id}/master/README.md",
                ]
                for cdn_url in cdn_urls:
                    try:
                        resp = await client.get(cdn_url, headers={"User-Agent": f"skills-but-for-dev/{__version__}"})
                        if resp.status_code == 200 and resp.text.strip():
                            raw_text = resp.text
                            break
                    except Exception:
                        pass

                # 2. Fallback to GitHub REST API if CDN misses
                if not raw_text:
                    headers = {"Accept": "application/vnd.github.raw+json", "User-Agent": f"skills-but-for-dev/{__version__}"}
                    if config.github_token:
                        headers["Authorization"] = f"Bearer {config.github_token}"
                    resp = await client.get(f"https://api.github.com/repos/{id}/readme", headers=headers)
                    if resp.status_code == 200:
                        raw_text = resp.text
                    elif resp.status_code in (403, 429):
                        return f"GitHub API rate limit exceeded when fetching README for {id}. Set GITHUB_TOKEN in environment."
            elif source == "hf_model":
                resp = await client.get(f"https://huggingface.co/{id}/raw/main/README.md")
                if resp.status_code == 200:
                    raw_text = resp.text
            elif source == "hf_space":
                resp = await client.get(f"https://huggingface.co/spaces/{id}/raw/main/README.md")
                if resp.status_code == 200:
                    raw_text = resp.text
    except Exception as e:
        return f"Error fetching documentation for {source}:{id}: {e}"

    if not raw_text:
        return f"No README.md documentation found for {source}:{id}."

    sanitized = sanitize_readme(raw_text, source, id, max_chars=max_chars)
    await cache.set(cache_key, sanitized, ttl_seconds=config.ttls.readme)
    return sanitized


@mcp.tool()
async def compare_candidates(ids: list[str]) -> dict:
    """Compare a list of repository or model identifiers side-by-side in a structured comparison table."""
    from skills_but_for_dev.github_client import github_client
    from skills_but_for_dev.hf_client import hf_client
    from skills_but_for_dev.pypi_client import pypi_client

    github_items = []
    hf_items = []

    for item_id in ids:
        if "/" in item_id:
            owner, repo = item_id.split("/", 1)
            # 1. Try GitHub repository first
            details = await github_client.get_repo_details(owner, repo)
            if details:
                if details.get("is_rate_limited"):
                    github_items.append({
                        "id": item_id,
                        "error": details.get("error"),
                    })
                else:
                    stars = details.get("stars", 0)
                    created_days = details.get("created_days_ago", 0)
                    vel, anomaly = await github_client.get_star_velocity(owner, repo, stars, created_days)
                    m_score = await github_client.get_repo_health(owner, repo)
                    pypi_downloads = await pypi_client.get_repo_downloads(repo)
                    github_items.append({
                        "id": item_id,
                        "stars": stars,
                        "forks": details.get("forks", 0),
                        "open_issues": details.get("open_issues", 0),
                        "license": details.get("license_class", "unknown"),
                        "license_spdx": details.get("license_spdx"),
                        "language": details.get("language"),
                        "description": details.get("description"),
                        "velocity_v4": vel.v4,
                        "acceleration": vel.accel,
                        "anomaly_warning": anomaly,
                        "maintenance_score": m_score,
                        "pypi_downloads_30d": pypi_downloads,
                        "last_pushed_days_ago": details.get("pushed_days_ago"),
                    })
            else:
                # 2. Check Hugging Face Hub
                try:
                    info = hf_client.api.model_info(item_id)
                    vram = await hf_client.calculate_vram_estimate(item_id)
                    hf_items.append({
                        "id": item_id,
                        "pipeline_tag": getattr(info, "pipeline_tag", None),
                        "downloads_30d": getattr(info, "downloads", 0) or 0,
                        "likes": getattr(info, "likes", 0) or 0,
                        "license": getattr(info, "cardData", {}).get("license") if hasattr(info, "cardData") and info.cardData else None,
                        "vram_min_gb": vram.min_gb,
                        "vram_variants": vram.variants,
                        "vram_note": vram.note,
                    })
                except Exception:
                    github_items.append({
                        "id": item_id,
                        "error": f"Repository or model '{item_id}' not found on GitHub or Hugging Face.",
                    })

    return {
        "comparison_table": {
            "github_repositories": github_items,
            "huggingface_models": hf_items,
        }
    }


def main():
    """Run MCP server via stdio transport, or provide CLI diagnostics."""
    import asyncio
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("--version", "-v"):
            print(f"skills-but-for-dev {__version__}")
            sys.exit(0)
        elif cmd in ("--help", "-h"):
            print(
                f"skills-but-for-dev v{__version__}: Intelligent tech stack & open-source curator for AI agents.\n\n"
                "Usage:\n"
                "  skills-but-for-dev                   Start MCP server (stdio transport, default)\n"
                "  skills-but-for-dev ping              Check server, token, and cache status\n"
                "  skills-but-for-dev --version         Display version\n"
                "  skills-but-for-dev --help            Display this help message\n"
            )
            sys.exit(0)
        elif cmd == "ping":
            print(asyncio.run(ping()))
            sys.exit(0)

    mcp.run()


if __name__ == "__main__":
    main()

