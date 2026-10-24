"""Configuration management for stack-scout."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict
from platformdirs import user_cache_dir
from dotenv import load_dotenv

load_dotenv()


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
    # API Tokens
    github_token: str | None = field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN") or None
    )
    hf_token: str | None = field(
        default_factory=lambda: os.getenv("HF_TOKEN") or None
    )

    # Cache directory
    cache_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("STACK_SCOUT_CACHE_DIR") or user_cache_dir("stack-scout", "stack-scout")
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
        # Override weights from STACK_SCOUT_WEIGHTS JSON env var if present
        raw_weights = os.getenv("STACK_SCOUT_WEIGHTS")
        if raw_weights:
            try:
                parsed = json.loads(raw_weights)
                for k, v in parsed.items():
                    if hasattr(self.weights, k):
                        setattr(self.weights, k, float(v))
            except Exception:
                pass


config = Settings()
