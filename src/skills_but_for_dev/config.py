"""Configuration management for skills-but-for-dev."""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_cache_dir

load_dotenv()
logger = logging.getLogger(__name__)


def detect_github_token() -> tuple[str | None, str]:
    """Detect GitHub token from ENV (GITHUB_TOKEN / GH_TOKEN) or GitHub CLI (gh auth token).

    Returns:
        (token, source) where source is 'env', 'gh_cli', or 'none'.
    """
    env_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip(), "env"

    gh_path = shutil.which("gh")
    if gh_path:
        try:
            res = subprocess.run(
                [gh_path, "auth", "token"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0:
                cli_token = res.stdout.strip()
                if cli_token and len(cli_token) > 8:
                    return cli_token, "gh_cli"
        except Exception as e:
            logger.debug("Failed checking gh CLI token: %s", e)

    return None, "none"


@dataclass
class ScoringWeights:
    # Stage 1: GitHub core weights (sum to 1.0)
    popularity: float = 0.25
    velocity: float = 0.30
    acceleration: float = 0.10
    recency: float = 0.20
    relevance: float = 0.15

    # Stage 2: Finalist re-ranking weights
    stage1_weight: float = 0.85
    maintenance_weight: float = 0.15

    # Prior assigned when signal is missing/failed (conservative baseline)
    prior: float = 0.25

    # HF Model weights (sum to 1.0)
    hf_adoption: float = 0.30
    hf_trending: float = 0.25
    hf_likes: float = 0.15
    hf_recency: float = 0.15
    hf_relevance: float = 0.15


@dataclass
class TTLSettings:
    github_search: int = 6 * 3600       # 6 hours
    star_history: int = 24 * 3600       # 24 hours
    repo_health: int = 24 * 3600        # 24 hours
    readme: int = 7 * 24 * 3600         # 7 days
    hf_search: int = 12 * 3600          # 12 hours
    hf_model_info: int = 3 * 24 * 3600  # 3 days


@dataclass
class Settings:
    # API Tokens & Discovery Source
    github_token: str | None = None
    token_source: str = "none"  # "env", "gh_cli", or "none"
    hf_token: str | None = field(
        default_factory=lambda: os.getenv("HF_TOKEN") or None
    )

    # Cache directory
    cache_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("SKILLS_BUT_FOR_DEV_CACHE_DIR") or user_cache_dir("skills-but-for-dev", "skills-but-for-dev")
        )
    )

    # Search & Candidate Quotas
    bucket_a_pushed_days: int = 120
    bucket_b_pushed_days: int = 30
    bucket_c_created_days: int = 365
    min_candidates_before_c: int = 15
    pre_score_quota_a: int = 6
    pre_score_quota_b: int = 6
    finalists_count: int = 3

    # Anomaly Detection (dormant_spike)
    dormant_spike_min_age_days: int = 180
    dormant_spike_min_stars: int = 200
    dormant_spike_ratio: float = 0.5
    dormant_spike_prior_weeks: int = 8
    dormant_spike_prior_max_avg: float = 5.0

    # Issue Responsiveness
    issue_censorship_days: int = 14
    issue_min_count_for_signal: int = 10

    # Weights & TTLs
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    ttls: TTLSettings = field(default_factory=TTLSettings)

    def __post_init__(self):
        # Auto-detect token if not already explicitly assigned
        if not self.github_token:
            token, source = detect_github_token()
            self.github_token = token
            self.token_source = source
        else:
            self.token_source = "env"

        # Override weights from SKILLS_BUT_FOR_DEV_WEIGHTS JSON env var if present
        raw_weights = os.getenv("SKILLS_BUT_FOR_DEV_WEIGHTS")
        if raw_weights:
            try:
                parsed = json.loads(raw_weights)
                for k, v in parsed.items():
                    if hasattr(self.weights, k):
                        setattr(self.weights, k, float(v))
            except Exception:
                pass


config = Settings()
