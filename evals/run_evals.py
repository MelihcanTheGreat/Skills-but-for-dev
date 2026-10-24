"""Evaluation runner for benchmarking accuracy, latency, cache efficiency, and enrichment."""

import asyncio
from pathlib import Path
import sys
import time

import yaml

# Ensure UTF-8 output on Windows terminal
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from skills_but_for_dev.cache import cache
from skills_but_for_dev.github_client import github_client
from skills_but_for_dev.hf_client import hf_client
from skills_but_for_dev.pypi_client import pypi_client


async def run_evaluation(queries_path: Path):
    with open(queries_path, encoding="utf-8") as f:
        cases = yaml.safe_load(f)

    print("\n=======================================================", flush=True)
    print("   SKILLS-BUT-FOR-DEV BENCHMARK & EVALUATION RUNNER    ", flush=True)
    print("=======================================================\n", flush=True)

    total_layers = 0
    total_hits = 0
    total_candidates_found = 0
    pypi_enriched_count = 0
    license_safe_count = 0
    cold_latencies = []
    cached_latencies = []

    for case in cases:
        print(f"[CASE] [{case['id']}] - {case['idea']}", flush=True)
        constraints = case.get("constraints", {})
        comm_use = constraints.get("commercial_use", False)
        max_vram = constraints.get("max_vram_gb")

        for layer in case["layers"]:
            total_layers += 1
            l_name = layer["name"]
            query = layer["query"]
            expect = layer.get("expect_any", [])

            # Measure cold search latency
            t0 = time.perf_counter()
            gh_res = await github_client.search_repositories(
                query=query,
                commercial_use=comm_use,
                limit=5,
            )
            cold_ms = (time.perf_counter() - t0) * 1000.0
            cold_latencies.append(cold_ms)

            # Measure cached search latency
            t_cache_0 = time.perf_counter()
            _ = await github_client.search_repositories(
                query=query,
                commercial_use=comm_use,
                limit=5,
            )
            cached_ms = (time.perf_counter() - t_cache_0) * 1000.0
            cached_latencies.append(cached_ms)

            # Track candidates and hits
            total_candidates_found += len(gh_res)
            top_names = [r.name.lower() for r in gh_res]
            hit = any(any(exp.lower() in name for exp in expect) for name in top_names) if expect else True
            if hit:
                total_hits += 1

            # Track PyPI stats and licenses
            for r in gh_res:
                if r.pypi_downloads_30d is not None and r.pypi_downloads_30d > 0:
                    pypi_enriched_count += 1
                if r.license_class in ("permissive", "commercial_ready", "mit", "apache-2.0", "bsd"):
                    license_safe_count += 1

            status = "PASS" if hit else "MISS"
            top_desc = gh_res[0].full_name if gh_res else "No match"
            pypi_stat = (
                f"{gh_res[0].pypi_downloads_30d:,}/mo"
                if gh_res and gh_res[0].pypi_downloads_30d
                else "N/A"
            )
            print(
                f"   Layer: {l_name:<16} [{status}] ({cold_ms:.0f}ms -> cache {cached_ms:.1f}ms)\n"
                f"          Top: {top_desc} | PyPI: {pypi_stat} | Lic: {gh_res[0].license_class if gh_res else 'N/A'}",
                flush=True,
            )

            # Optional HF Search
            if layer.get("hf_task"):
                hf_res = await hf_client.search_models(
                    query=query.split()[0],
                    task=layer["hf_task"],
                    max_vram_gb=max_vram,
                    commercial_use=comm_use,
                    limit=2,
                )
                if hf_res:
                    top_m = hf_res[0]
                    vram_str = f"{top_m.vram.min_gb}GB" if top_m.vram and top_m.vram.min_gb else "N/A"
                    print(f"          HF:  {top_m.id} | DL: {top_m.downloads_30d:,} | VRAM: {vram_str}", flush=True)

        print(flush=True)

    # Calculate overall metrics
    hit_rate = (total_hits / max(1, total_layers)) * 100
    avg_cold_ms = sum(cold_latencies) / max(1, len(cold_latencies))
    avg_cached_ms = sum(cached_latencies) / max(1, len(cached_latencies))
    speedup = avg_cold_ms / max(0.1, avg_cached_ms)
    pypi_rate = (pypi_enriched_count / max(1, total_candidates_found)) * 100
    license_rate = (license_safe_count / max(1, total_candidates_found)) * 100

    print("=======================================================", flush=True)
    print("                EVALUATION SCORECARD                   ", flush=True)
    print("=======================================================", flush=True)
    print(f"Hit Rate (Accuracy @ 5):      {hit_rate:.1f}% ({total_hits}/{total_layers} layers passed)", flush=True)
    print(f"Avg Cold Latency:             {avg_cold_ms:.1f} ms", flush=True)
    print(f"Avg Cached Latency:           {avg_cached_ms:.2f} ms", flush=True)
    print(f"Cache Speedup Multiplier:     {speedup:.1f}x faster", flush=True)
    print(f"PyPI Adoption Sinyal Orani:   {pypi_rate:.1f}% ({pypi_enriched_count}/{total_candidates_found} aday)", flush=True)
    print(f"Ticari Lisans Uyumu:          {license_rate:.1f}%", flush=True)
    print("=======================================================\n", flush=True)

    await github_client.close()
    await pypi_client.close()
    await cache.close()


if __name__ == "__main__":
    path = Path(__file__).parent / "queries.yaml"
    asyncio.run(run_evaluation(path))
