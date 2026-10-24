"""Data models and schemas for skills-but-for-dev."""

from typing import Literal

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
    v4: float | None = None  # Daily star avg over last 4 weeks (28 days)
    v12: float | None = None  # Daily star avg over last 12 weeks (84 days)
    accel: float | None = None  # v4 / v12 (acceleration factor, >1 accelerating)
    rel_v4: float | None = None  # v4 / total_stars (relative growth)
    source: Literal["history", "unavailable"] = "history"


class RepoScoreBreakdown(BaseModel):
    popularity: float
    velocity: float
    acceleration: float
    recency: float
    relevance: float
    maintenance: float | None = None
    pypi_adoption: float | None = None
    priors_used: list[str] = Field(default_factory=list)


class GitHubRepoCandidate(BaseModel):
    full_name: str
    name: str
    owner: str
    url: str
    description: str | None = None
    stars: int
    pushed_days_ago: int
    created_days_ago: int
    license_spdx: str | None = None
    license_class: LicenseClass = "unknown"
    topics: list[str] = Field(default_factory=list)
    bucket: Literal["A", "B", "C"]
    velocity: StarVelocity | None = None
    score: float = 0.0
    score_breakdown: RepoScoreBreakdown | None = None
    confidence: ConfidenceLevel = "high"
    anomaly_warning: str | None = None  # e.g., "dormant_spike"
    is_finalist: bool = False
    maintenance_score: float | None = None
    pypi_downloads_30d: int | None = None


class VramEstimate(BaseModel):
    method: Literal[
        "safetensors_params",
        "file_size",
        "gguf_variants",
        "diffusers",
        "unknown",
    ]
    min_gb: float | None = None
    variants: dict[str, float] | None = None  # e.g., {"Q4_K_M": 4.9, "Q8_0": 8.5}
    note: str = "Ağırlık belleği alt sınırı; KV-cache, aktivasyon ve girdi uzunluğu hariçtir."


class HFModelCandidate(BaseModel):
    id: str
    url: str
    task: str | None = None
    downloads_30d: int = 0
    likes: int = 0
    trending_score: float | None = None
    last_modified_days_ago: int = 0
    license: str | None = None
    license_class: LicenseClass = "unknown"
    vram: VramEstimate | None = None
    score: float = 0.0


class HFSpaceCandidate(BaseModel):
    id: str
    url: str
    sdk: str | None = None
    likes: int = 0
    last_modified_days_ago: int = 0
    running: bool = True


class UntrustedContent(BaseModel):
    source: Literal["github", "hf_model", "hf_space"]
    id: str
    content: str
    fetched_at: str
    truncated: bool = False
