"""Hugging Face Hub client with VRAM estimation, model and Space search."""

import asyncio
import datetime
import logging
import math
import re

from huggingface_hub import HfApi

from skills_but_for_dev.cache import cache, make_cache_key
from skills_but_for_dev.config import config
from skills_but_for_dev.licenses import classify_license
from skills_but_for_dev.models import (
    HFModelCandidate,
    HFSpaceCandidate,
    VramEstimate,
)
from skills_but_for_dev.scoring import calculate_license_penalty

logger = logging.getLogger(__name__)


def _days_since(dt: datetime.datetime | None) -> int:
    if not dt:
        return 9999
    now = datetime.datetime.now(datetime.UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    return max(0, (now - dt).days)


class HFClient:
    """Hugging Face API client with memory/VRAM calculation and score ranking."""

    def __init__(self):
        self.api = HfApi(token=config.hf_token)

    async def calculate_vram_estimate(self, model_id: str) -> VramEstimate:
        """Estimate minimum GPU VRAM requirement handling safetensors params, sharded weights, GGUF variants, and diffusers."""
        cache_key = make_cache_key("hf_vram", model_id=model_id)
        cached = await cache.get(cache_key)
        if cached is not None:
            return VramEstimate(**cached)

        try:
            # Fetch model metadata including files
            info = self.api.model_info(model_id, files_metadata=True)

            # Strategy 1: Explicit safetensors total parameters
            if getattr(info, "safetensors", None) and hasattr(info.safetensors, "total"):
                total_params = info.safetensors.total
                if total_params and total_params > 0:
                    # Estimate standard 16-bit float (2 bytes per param) * 1.2 overhead
                    min_gb = (total_params * 2.0 * 1.2) / (1024**3)
                    est = VramEstimate(
                        method="safetensors_params",
                        min_gb=round(min_gb, 2),
                        note=f"safetensors ({total_params:,} parametre, FP16 tabanlı alt sınır)",
                    )
                    await cache.set(cache_key, est.model_dump(), ttl_seconds=config.ttls.hf_model_info)
                    return est

            siblings = getattr(info, "siblings", []) or []
            file_names = [s.rfilename for s in siblings if hasattr(s, "rfilename")]
            file_sizes = {s.rfilename: getattr(s, "size", 0) or 0 for s in siblings if hasattr(s, "rfilename")}

            # Strategy 2: GGUF Quantization variants (do NOT sum them together!)
            gguf_files = [f for f in file_names if f.lower().endswith(".gguf")]
            if gguf_files:
                variants: dict[str, float] = {}
                # Match standard quantization patterns like Q4_K_M, Q5_K_M, Q8_0, etc.
                quant_re = re.compile(r"([qQ]\d+_[a-zA-Z0-9_]+|[fF]16|[fF]32)")
                for gf in gguf_files:
                    match = quant_re.search(gf)
                    tag = match.group(1).upper() if match else "DEFAULT"
                    sz_gb = (file_sizes.get(gf, 0) * 1.2) / (1024**3)
                    # For sharded gguf, accumulate
                    variants[tag] = round(variants.get(tag, 0.0) + sz_gb, 2)

                # Pick popular reference quantizations if available
                ref_min = variants.get("Q4_K_M") or variants.get("Q4_0") or next(iter(variants.values()), 0.0)
                est = VramEstimate(
                    method="gguf_variants",
                    min_gb=ref_min,
                    variants=variants,
                    note="GGUF kuantizasyon varyantları ayrı ayrı hesaplanmıştır (toplanmaz).",
                )
                await cache.set(cache_key, est.model_dump(), ttl_seconds=config.ttls.hf_model_info)
                return est

            # Strategy 3: Diffusers pipelines (model_index.json present -> subfolders are components!)
            if "model_index.json" in file_names:
                total_bytes = 0
                # Identify components: each top-level directory (e.g. unet/, vae/, text_encoder/)
                component_dirs = set(f.split("/")[0] for f in file_names if "/" in f)
                for c_dir in component_dirs:
                    dir_files = [f for f in file_names if f.startswith(f"{c_dir}/")]
                    # Pick single format per component dir (safetensors > bin > onnx)
                    chosen_fmt = None
                    for fmt in [".safetensors", ".bin", ".onnx"]:
                        if any(f.endswith(fmt) for f in dir_files):
                            chosen_fmt = fmt
                            break
                    if chosen_fmt:
                        for f in dir_files:
                            if f.endswith(chosen_fmt) and "consolidated" not in f.lower():
                                total_bytes += file_sizes.get(f, 0)

                if total_bytes > 0:
                    min_gb = (total_bytes * 1.2) / (1024**3)
                    est = VramEstimate(
                        method="diffusers",
                        min_gb=round(min_gb, 2),
                        note="Diffusers boru hattı bileşenleri (unet, vae vb.) toplanarak hesaplanmıştır.",
                    )
                    await cache.set(cache_key, est.model_dump(), ttl_seconds=config.ttls.hf_model_info)
                    return est

            # Strategy 4: Standard single format with sharded files (e.g. model-00001-of-00003.safetensors)
            chosen_format = None
            for fmt in [".safetensors", ".bin", ".onnx"]:
                if any(f.endswith(fmt) for f in file_names):
                    chosen_format = fmt
                    break

            if chosen_format:
                matching_files = [
                    f for f in file_names
                    if f.endswith(chosen_format)
                    and "/" not in f  # exclude subfolder alternative copies
                    and "consolidated" not in f.lower()
                    and "original" not in f.lower()
                ]
                total_bytes = sum(file_sizes.get(f, 0) for f in matching_files)
                if total_bytes > 0:
                    min_gb = (total_bytes * 1.2) / (1024**3)
                    est = VramEstimate(
                        method="file_size",
                        min_gb=round(min_gb, 2),
                        note=f"{chosen_format} ağırlık dosyaları toplamı ({len(matching_files)} parça)",
                    )
                    await cache.set(cache_key, est.model_dump(), ttl_seconds=config.ttls.hf_model_info)
                    return est

        except Exception as e:
            logger.debug("Failed VRAM calculation for %s: %s", model_id, e)

        return VramEstimate(
            method="unknown",
            min_gb=None,
            note="Model dosya yapısından VRAM alt sınırı otomatik okunamadı.",
        )

    async def search_models(
        self,
        query: str,
        task: str | None = None,
        max_vram_gb: float | None = None,
        commercial_use: bool = False,
        limit: int = 8,
    ) -> list[HFModelCandidate]:
        """Search Hugging Face models by keyword and task with VRAM calculation and scoring."""
        cache_key = make_cache_key(
            "hf_search_models", query=query, task=task, commercial=commercial_use
        )
        cached = await cache.get(cache_key)

        if cached is not None:
            candidates = [HFModelCandidate(**item) for item in cached]
        else:
            candidates = []
            try:
                # Query Hugging Face Hub
                models_iter = self.api.list_models(
                    search=query,
                    pipeline_tag=task,
                    limit=30,
                    expand=[
                        "downloads",
                        "likes",
                        "trendingScore",
                        "lastModified",
                        "pipeline_tag",
                        "cardData",
                        "safetensors",
                    ],
                )
                raw_models = list(models_iter)

                # Pre-calculate trending range for min-max normalization
                trend_scores = [getattr(m, "trending_score", 0.0) or 0.0 for m in raw_models]
                max_trend = max(trend_scores) if trend_scores else 1.0
                min_trend = min(trend_scores) if trend_scores else 0.0
                trend_range = max(1.0, max_trend - min_trend)

                w = config.weights
                for m in raw_models:
                    model_id = m.id
                    downloads = getattr(m, "downloads", 0) or 0
                    likes = getattr(m, "likes", 0) or 0
                    trend = getattr(m, "trending_score", 0.0) or 0.0
                    last_mod_ago = _days_since(getattr(m, "last_modified", None))

                    # License info from cardData
                    card = getattr(m, "card_data", None) or {}
                    raw_lic = card.get("license") if isinstance(card, dict) else None
                    lic_class = classify_license(raw_lic)

                    # Scoring components
                    s_adopt = min(1.0, math.log10(downloads + 1) / 7.0)
                    s_trend = min(1.0, max(0.0, (trend - min_trend) / trend_range))
                    s_likes = min(1.0, math.log10(likes + 1) / 4.0)
                    s_rec = math.exp(-last_mod_ago / 180.0)
                    s_rel = 1.0 if query.lower() in model_id.lower() else 0.5

                    base_score = (
                        w.hf_adoption * s_adopt
                        + w.hf_trending * s_trend
                        + w.hf_likes * s_likes
                        + w.hf_recency * s_rec
                        + w.hf_relevance * s_rel
                    )
                    penalty = calculate_license_penalty(lic_class, commercial_use=commercial_use)
                    final_score = max(0.0, base_score - penalty)

                    candidate = HFModelCandidate(
                        id=model_id,
                        url=f"https://huggingface.co/{model_id}",
                        task=getattr(m, "pipeline_tag", None),
                        downloads_30d=downloads,
                        likes=likes,
                        trending_score=round(trend, 2) if trend else None,
                        last_modified_days_ago=last_mod_ago,
                        license=raw_lic,
                        license_class=lic_class,
                        score=round(final_score, 4),
                    )
                    candidates.append(candidate)

                candidates.sort(key=lambda c: c.score, reverse=True)
                await cache.set(
                    cache_key,
                    [c.model_dump() for c in candidates],
                    ttl_seconds=config.ttls.hf_search,
                )
            except Exception as e:
                logger.error("Hugging Face model search error: %s", e)
                return []

        # Compute VRAM estimates for top candidates concurrently
        eval_pool = candidates[: limit * 2]
        vrams = await asyncio.gather(*[self.calculate_vram_estimate(c.id) for c in eval_pool])
        for c, vram in zip(eval_pool, vrams):
            c.vram = vram

        filtered: list[HFModelCandidate] = []
        for c in eval_pool:
            if max_vram_gb is not None and c.vram and c.vram.min_gb is not None:
                if c.vram.min_gb > max_vram_gb:
                    continue  # Exceeds user hardware constraint!
            filtered.append(c)
            if len(filtered) >= limit:
                break

        return filtered

    async def search_spaces(self, query: str, limit: int = 5) -> list[HFSpaceCandidate]:
        """Search Hugging Face Spaces for running live demonstrations."""
        cache_key = make_cache_key("hf_search_spaces", query=query)
        cached = await cache.get(cache_key)
        if cached is not None:
            return [HFSpaceCandidate(**it) for it in cached][:limit]

        try:
            spaces_iter = self.api.list_spaces(search=query, sort="likes", limit=15)
            spaces = []
            for sp in spaces_iter:
                last_mod_ago = _days_since(getattr(sp, "last_modified", None))
                spaces.append(
                    HFSpaceCandidate(
                        id=sp.id,
                        url=f"https://huggingface.co/spaces/{sp.id}",
                        sdk=getattr(sp, "sdk", None),
                        likes=getattr(sp, "likes", 0) or 0,
                        last_modified_days_ago=last_mod_ago,
                    )
                )

            await cache.set(
                cache_key,
                [s.model_dump() for s in spaces],
                ttl_seconds=config.ttls.hf_search,
            )
            return spaces[:limit]
        except Exception as e:
            logger.error("Hugging Face Spaces search error: %s", e)
            return []


hf_client = HFClient()

