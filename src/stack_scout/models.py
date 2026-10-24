"""Data models and schemas for stack-scout."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

LicenseClass = Literal[
    "permissive",
    "weak_copyleft",
    "strong_copyleft",
    "non_commercial",
    "custom",
    "unknown",
]

ConfidenceLevel = Literal["high", "low"]


class StarVelocity(BaseModel):
    v4: Optional[float] = None  # Daily star avg over last 4 weeks (28 days)
    v12: Optional[float] = None  # Daily star avg over last 12 weeks (84 days)
    accel: Optional[float] = None  # v4 / v12 (acceleration factor, >1 accelerating)
    rel_v4: Optional[float] = None  # v4 / total_stars (relative growth)
    source: Literal["history", "unavailable"] = "history"


class RepoScoreBreakdown(BaseModel):
    popularity: float
    velocity: float
    acceleration: float
    recency: float
    relevance: float
    maintenance: Optional[float] = None
    priors_used: List[str] = Field(default_factory=list)


class GitHubRepoCandidate(BaseModel):
    full_name: str
    name: str
    owner: str
    url: str
    description: Optional[str] = None
    stars: int
    pushed_days_ago: int
    created_days_ago: int
    license_spdx: Optional[str] = None
    license_class: LicenseClass = "unknown"
    topics: List[str] = Field(default_factory=list)
    bucket: Literal["A", "B", "C"]
    velocity: Optional[StarVelocity] = None
    score: float = 0.0
    score_breakdown: Optional[RepoScoreBreakdown] = None
    confidence: ConfidenceLevel = "high"
    anomaly_warning: Optional[str] = None  # e.g., "dormant_spike"
    is_finalist: bool = False
    maintenance_score: Optional[float] = None


class VramEstimate(BaseModel):
    method: Literal[
        "safetensors_params",
        "file_size",
        "gguf_variants",
        "diffusers",
        "unknown",
    ]
    min_gb: Optional[float] = None
    variants: Optional[Dict[str, float]] = None  # e.g., {"Q4_K_M": 4.9, "Q8_0": 8.5}
    note: str = "Ağırlık belleği alt sınırı; KV-cache, aktivasyon ve girdi uzunluğu hariçtir."


class HFModelCandidate(BaseModel):
    id: str
    url: str
    task: Optional[str] = None
    downloads_30d: int = 0
    likes: int = 0
    trending_score: Optional[float] = None
    last_modified_days_ago: int = 0
    license: Optional[str] = None
    license_class: LicenseClass = "unknown"
    vram: Optional[VramEstimate] = None
    score: float = 0.0


class HFSpaceCandidate(BaseModel):
    id: str
    url: str
    sdk: Optional[str] = None
    likes: int = 0
    last_modified_days_ago: int = 0
    running: bool = True


class UntrustedContent(BaseModel):
    source: Literal["github", "hf_model", "hf_space"]
    id: str
    content: str
    fetched_at: str
    truncated: bool = False
