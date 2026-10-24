"""Evaluation runner for measuring recommendation hit rate, freshness, and license compliance."""

import asyncio
from pathlib import Path

import yaml

from skills_but_for_dev.cache import cache
from skills_but_for_dev.github_client import github_client
from skills_but_for_dev.hf_client import hf_client


async def run_evaluation(queries_path: Path):
    with open(queries_path, encoding="utf-8") as f:
        cases = yaml.safe_load(f)

    print("\n=======================================================")
    print("   SKILLS-BUT-FOR-DEV EVALUATION RUNNER (EVALS)        ")
    print("=======================================================\n")

    total_layers = 0
    total_hits = 0

    for case in cases:
        print(f"🧪 Case: [{case['id']}] - {case['idea']}")
        constraints = case.get("constraints", {})
        comm_use = constraints.get("commercial_use", False)
        max_vram = constraints.get("max_vram_gb")

        for layer in case["layers"]:
            total_layers += 1
            l_name = layer["name"]
            query = layer["query"]
            expect = layer.get("expect_any", [])

            # Run GitHub Search
            gh_res = await github_client.search_repositories(
                query=query,
                commercial_use=comm_use,
                limit=5,
            )

            top_names = [r.name.lower() for r in gh_res]
            hit = any(any(exp.lower() in name for exp in expect) for name in top_names) if expect else True
            if hit:
                total_hits += 1

            status = "✅ PASS" if hit else "⚠️ MISS"
            print(f"   Layer: {l_name:<15} [{status}] Query: '{query}'")
            if gh_res:
                top_repo = gh_res[0]
                accel = top_repo.velocity.accel if top_repo.velocity else None
                print(f"      Top Match: {top_repo.full_name} | Stars: {top_repo.stars} | Accel: {accel} | Lic: {top_repo.license_class}")

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
                    print(f"      Top HF Model: {top_m.id} | Downloads: {top_m.downloads_30d:,} | VRAM: {vram_str}")

        print()

    hit_rate = (total_hits / max(1, total_layers)) * 100
    print("-------------------------------------------------------")
    print(f"SUMMARY: Total Layers: {total_layers} | Hits@5: {total_hits} | Hit Rate: {hit_rate:.1f}%")
    print("=======================================================\n")

    await github_client.close()
    await cache.close()


if __name__ == "__main__":
    path = Path(__file__).parent / "queries.yaml"
    asyncio.run(run_evaluation(path))

