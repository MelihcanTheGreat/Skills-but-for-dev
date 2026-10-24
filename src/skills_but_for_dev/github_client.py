"""GitHub REST client with dual-bucket candidate retrieval, star velocity and health metrics."""

import asyncio
import datetime
import logging
import statistics
from typing import Any

import httpx

from skills_but_for_dev import __version__
from skills_but_for_dev.cache import cache, make_cache_key
from skills_but_for_dev.config import config
from skills_but_for_dev.licenses import classify_license, is_commercially_viable
from skills_but_for_dev.models import (
    GitHubRepoCandidate,
    StarVelocity,
)
from skills_but_for_dev.pypi_client import pypi_client
from skills_but_for_dev.query_normalizer import normalize_query
from skills_but_for_dev.ratelimit import rate_limiter
from skills_but_for_dev.scoring import (
    calculate_popularity_score,
    calculate_recency_score,
    calculate_relevance_score,
    score_stage1,
    score_stage2_finalists,
)

logger = logging.getLogger(__name__)
BASE_URL = "https://api.github.com"


def _get_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"skills-but-for-dev/{__version__}",
    }
    if config.github_token:
        headers["Authorization"] = f"Bearer {config.github_token}"
    return headers


def _days_since(iso_str: str | None) -> int:
    if not iso_str:
        return 9999
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.UTC)
        return max(0, (now - dt).days)
    except Exception:
        return 9999


class GitHubClient:
    """Handles GitHub API calls with caching, rate limit compliance, and dual-bucket search."""

    def __init__(self):
        self._http_client: httpx.AsyncClient | None = None

    @property
    def http_client(self) -> httpx.AsyncClient:
        is_closed = getattr(self._http_client, "is_closed", False)
        # If is_closed is a mock object (not boolean), treat it as False
        if not isinstance(is_closed, bool):
            is_closed = False
        if self._http_client is None or is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=15.0, headers=_get_headers(), follow_redirects=True
            )
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        await pypi_client.close()

    async def _search_raw(self, query: str, sort: str | None = None) -> list[dict[str, Any]]:
        """Execute raw GitHub repository search with rate limit protection and caching."""
        cache_key = make_cache_key("github_search", query=query, sort=sort)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        await rate_limiter.acquire_search_slot()
        params = {"q": query, "per_page": 30}
        if sort:
            params["sort"] = sort

        try:
            resp = await self.http_client.get(f"{BASE_URL}/search/repositories", params=params)
            rate_limiter.update_from_headers(resp, is_search=True)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                await cache.set(cache_key, items, ttl_seconds=config.ttls.github_search)
                return items
            else:
                logger.warning("GitHub search failed [%s]: %s", resp.status_code, resp.text)
                return []
        except Exception as e:
            logger.error("GitHub search request error: %s", e)
            return []

    async def get_star_velocity(
        self, owner: str, repo: str, stars: int, created_days_ago: int
    ) -> tuple[StarVelocity, str | None]:
        """Fetch weekly star history via GET /repos/{owner}/{repo}/stargazers/history and check anomaly."""
        cache_key = make_cache_key("star_velocity", owner=owner, repo=repo)
        cached = await cache.get(cache_key)
        if cached is not None:
            vel = StarVelocity(**cached["velocity"])
            return vel, cached.get("anomaly_warning")

        url = f"{BASE_URL}/repos/{owner}/{repo}/stargazers/history"
        try:
            resp = await self.http_client.get(url, params={"per_page": 30})
            rate_limiter.update_from_headers(resp, is_search=False)

            if resp.status_code != 200:
                logger.debug("stargazers/history returned %s for %s/%s", resp.status_code, owner, repo)
                return StarVelocity(source="unavailable"), None

            weeks_data = resp.json()
            if not isinstance(weeks_data, list):
                return StarVelocity(source="unavailable"), None

            totals = [int(w.get("total", 0)) for w in weeks_data if isinstance(w, dict)]

            # Compute v4 and v12
            weeks_count = len(totals)
            if weeks_count == 0:
                return StarVelocity(v4=0.0, v12=0.0, accel=1.0, rel_v4=0.0, source="history"), None

            w4_slice = totals[:4]
            days_4 = len(w4_slice) * 7
            v4 = sum(w4_slice) / max(1, days_4)

            w12_slice = totals[:12]
            days_12 = len(w12_slice) * 7
            v12 = sum(w12_slice) / max(1, days_12)

            accel = v4 / max(v12, 0.1)
            rel_v4 = v4 / max(stars, 1)

            vel = StarVelocity(
                v4=round(v4, 2),
                v12=round(v12, 2),
                accel=round(accel, 2),
                rel_v4=round(rel_v4, 5),
                source="history",
            )

            # Check dormant_spike anomaly
            anomaly_warning = None
            if (
                created_days_ago > config.dormant_spike_min_age_days
                and stars > config.dormant_spike_min_stars
            ):
                for i in range(min(4, len(totals))):
                    if totals[i] > (config.dormant_spike_ratio * stars):
                        # Check prior 8 weeks
                        prior_weeks = totals[i + 1 : i + 1 + config.dormant_spike_prior_weeks]
                        if prior_weeks:
                            prior_avg = sum(prior_weeks) / len(prior_weeks)
                            if prior_avg < config.dormant_spike_prior_max_avg:
                                anomaly_warning = "dormant_spike"
                                break

            # Cache velocity and anomaly result
            await cache.set(
                cache_key,
                {"velocity": vel.model_dump(), "anomaly_warning": anomaly_warning},
                ttl_seconds=config.ttls.star_history,
            )
            return vel, anomaly_warning

        except Exception as e:
            logger.warning("Error fetching star velocity for %s/%s: %s", owner, repo, e)
            return StarVelocity(source="unavailable"), None

    async def get_repo_health(self, owner: str, repo: str) -> float | None:
        """Fetch releases, contributors, and issue responsiveness to compute maintenance score (0.0 - 1.0)."""
        cache_key = make_cache_key("repo_health", owner=owner, repo=repo)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached.get("maintenance_score")

        signals: list[float] = []

        if not rate_limiter.can_make_core_request(min_remaining=3):
            logger.info("Preserving GitHub Core API limit (remaining <= 3), assigning prior maintenance score.")
            return None

        try:
            # Parallel fetch releases, contributors, and issues
            rel_task = self.http_client.get(
                f"{BASE_URL}/repos/{owner}/{repo}/releases", params={"per_page": 10}
            )
            con_task = self.http_client.get(
                f"{BASE_URL}/repos/{owner}/{repo}/contributors", params={"per_page": 1, "anon": "0"}
            )
            issue_task = self.http_client.get(
                f"{BASE_URL}/repos/{owner}/{repo}/issues",
                params={"state": "all", "sort": "created", "direction": "desc", "per_page": 100},
            )

            rel_resp, con_resp, issue_resp = await asyncio.gather(
                rel_task, con_task, issue_task, return_exceptions=True
            )

            # 1. Releases cadence
            if isinstance(rel_resp, httpx.Response) and rel_resp.status_code == 200:
                rate_limiter.update_from_headers(rel_resp, is_search=False)
                releases = rel_resp.json()
                if len(releases) >= 2:
                    dates = [
                        datetime.datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
                        for r in releases
                        if r.get("published_at")
                    ]
                    intervals = [abs((dates[i] - dates[i + 1]).days) for i in range(len(dates) - 1)]
                    median_interval = statistics.median(intervals) if intervals else 180
                    rel_score = max(0.0, min(1.0, 1.0 - (median_interval / 180.0)))
                    signals.append(rel_score)

            # 2. Contributors count from Link header
            if isinstance(con_resp, httpx.Response) and con_resp.status_code == 200:
                rate_limiter.update_from_headers(con_resp, is_search=False)
                link_header = con_resp.headers.get("link", "")
                if 'rel="last"' in link_header:
                    import re
                    match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
                    if match:
                        total_contributors = int(match.group(1))
                        con_score = min(1.0, total_contributors / 50.0)
                        signals.append(con_score)

            # 3. Issues responsiveness
            if isinstance(issue_resp, httpx.Response) and issue_resp.status_code == 200:
                rate_limiter.update_from_headers(issue_resp, is_search=False)
                items = issue_resp.json()
                pure_issues = [it for it in items if isinstance(it, dict) and "pull_request" not in it]
                now = datetime.datetime.now(datetime.UTC)
                eligible_issues = []
                for it in pure_issues:
                    c_at = it.get("created_at")
                    if c_at:
                        age = (now - datetime.datetime.fromisoformat(c_at.replace("Z", "+00:00"))).days
                        if age >= config.issue_censorship_days:
                            eligible_issues.append(it)

                if len(eligible_issues) >= config.issue_min_count_for_signal:
                    closed = [it for it in eligible_issues if it.get("state") == "closed"]
                    closed_ratio = len(closed) / len(eligible_issues)

                    close_durations = []
                    for it in closed:
                        c_at = it.get("created_at")
                        cl_at = it.get("closed_at")
                        if c_at and cl_at:
                            dur = (
                                datetime.datetime.fromisoformat(cl_at.replace("Z", "+00:00"))
                                - datetime.datetime.fromisoformat(c_at.replace("Z", "+00:00"))
                            ).days
                            close_durations.append(max(0, dur))

                    med_days = statistics.median(close_durations) if close_durations else 30
                    speed_score = max(0.0, min(1.0, 1.0 - (med_days / 60.0)))
                    issue_score = 0.6 * closed_ratio + 0.4 * speed_score
                    signals.append(issue_score)

            maintenance_score = round(sum(signals) / len(signals), 3) if signals else None
            await cache.set(
                cache_key,
                {"maintenance_score": maintenance_score},
                ttl_seconds=config.ttls.repo_health,
            )
            return maintenance_score

        except Exception as e:
            logger.warning("Error computing repo health for %s/%s: %s", owner, repo, e)
            return None

    async def get_repo_details(self, owner: str, repo: str) -> dict[str, Any] | None:
        """Fetch general repository metadata from GET /repos/{owner}/{repo} with caching."""
        cache_key = make_cache_key("repo_details", owner=owner, repo=repo)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            resp = await self.http_client.get(f"{BASE_URL}/repos/{owner}/{repo}")
            rate_limiter.update_from_headers(resp, is_search=False)
            if resp.status_code == 200:
                data = resp.json()
                lic_spdx = data.get("license", {}).get("spdx_id") if data.get("license") else None
                details = {
                    "owner": owner,
                    "repo": repo,
                    "full_name": f"{owner}/{repo}",
                    "description": data.get("description") or "",
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "open_issues": data.get("open_issues_count", 0),
                    "language": data.get("language"),
                    "license_spdx": lic_spdx,
                    "license_class": classify_license(lic_spdx),
                    "created_at": data.get("created_at"),
                    "pushed_at": data.get("pushed_at"),
                    "created_days_ago": _days_since(data.get("created_at")),
                    "pushed_days_ago": _days_since(data.get("pushed_at")),
                }
                await cache.set(cache_key, details, ttl_seconds=config.ttls.repo_health)
                return details
            elif resp.status_code in (403, 429):
                err_msg = rate_limiter.last_core_error or f"GitHub Core API rate limit reached (HTTP {resp.status_code})"
                logger.warning("GET /repos/%s/%s rate limited: %s", owner, repo, err_msg)
                return {"error": err_msg, "is_rate_limited": True, "full_name": f"{owner}/{repo}"}
            else:
                logger.warning("GET /repos/%s/%s returned %s", owner, repo, resp.status_code)
                return None
        except Exception as e:
            logger.warning("Error fetching repo details for %s/%s: %s", owner, repo, e)
            return None

    def _parse_raw_candidate(self, item: dict[str, Any], bucket: str) -> GitHubRepoCandidate:
        full_name = item.get("full_name", "")
        parts = full_name.split("/")
        owner = parts[0] if parts else ""
        name = parts[1] if len(parts) > 1 else full_name

        license_info = item.get("license") or {}
        spdx = license_info.get("spdx_id")
        lic_class = classify_license(spdx or license_info.get("name"))

        pushed_ago = _days_since(item.get("pushed_at"))
        created_ago = _days_since(item.get("created_at"))

        return GitHubRepoCandidate(
            full_name=full_name,
            name=name,
            owner=owner,
            url=item.get("html_url", f"https://github.com/{full_name}"),
            description=item.get("description"),
            stars=item.get("stargazers_count", 0),
            pushed_days_ago=pushed_ago,
            created_days_ago=created_ago,
            license_spdx=spdx,
            license_class=lic_class,
            topics=item.get("topics", []) or [],
            bucket=bucket,  # type: ignore
        )

    async def search_repositories(
        self,
        query: str,
        topics: list[str] | None = None,
        language: str | None = None,
        commercial_use: bool = False,
        limit: int = 8,
    ) -> list[GitHubRepoCandidate]:
        """Search repositories using dual-bucket logic, pre-scoring quotas, star velocity, and health ranking."""
        now = datetime.datetime.now(datetime.UTC)
        date_a = (now - datetime.timedelta(days=config.bucket_a_pushed_days)).strftime("%Y-%m-%d")
        date_b = (now - datetime.timedelta(days=config.bucket_b_pushed_days)).strftime("%Y-%m-%d")
        date_c = (now - datetime.timedelta(days=config.bucket_c_created_days)).strftime("%Y-%m-%d")

        norm = normalize_query(query)
        effective_query = norm.cleaned_query if norm.cleaned_query else query
        query_terms = norm.terms if norm.terms else [t for t in query.strip().split() if t][:3]
        base_query = effective_query

        if topics:
            for top in topics[:2]:
                base_query += f" topic:{top}"
        if language:
            base_query += f" language:{language}"

        # 1. Fetch Bucket A (Leaders, sort=stars)
        q_a = f"{base_query} stars:>500 pushed:>{date_a} fork:false archived:false"
        items_a = await self._search_raw(q_a, sort="stars")
        candidates_a = [self._parse_raw_candidate(it, "A") for it in items_a]

        # 2. Fetch Bucket B (Momentum/Rising, sort=best match)
        q_b = f"{base_query} stars:75..3500 pushed:>{date_b} fork:false archived:false"
        items_b = await self._search_raw(q_b, sort=None)
        candidates_b = [self._parse_raw_candidate(it, "B") for it in items_b]

        # 3. Optional Bucket C (Backup if sparse)
        candidates_c: list[GitHubRepoCandidate] = []
        if len(candidates_a) + len(candidates_b) < config.min_candidates_before_c:
            q_c = f"{base_query} created:>{date_c} stars:>30 fork:false archived:false"
            items_c = await self._search_raw(q_c, sort=None)
            candidates_c = [self._parse_raw_candidate(it, "C") for it in items_c]

        # Deduplicate: if repo in multiple buckets, A takes precedence
        seen_names = set()
        deduped_a = []
        for c in candidates_a:
            if c.full_name not in seen_names:
                seen_names.add(c.full_name)
                deduped_a.append(c)

        deduped_b = []
        for c in candidates_b + candidates_c:
            if c.full_name not in seen_names:
                seen_names.add(c.full_name)
                deduped_b.append(c)

        # 4. Per-bucket pre-scoring without history API calls
        def pre_score_a(c: GitHubRepoCandidate) -> float:
            pop = calculate_popularity_score(c.stars)
            rec = calculate_recency_score(c.pushed_days_ago)
            rel = calculate_relevance_score(query_terms, c.name, c.description, c.topics)
            lic_ok = 1.0 if is_commercially_viable(c.license_class) else 0.0
            return 0.35 * pop + 0.30 * rel + 0.25 * rec + 0.10 * lic_ok

        def pre_score_b(c: GitHubRepoCandidate) -> float:
            # NO log_stars in pre_score_b to avoid crushing genuine low-star breakout repos!
            rec = calculate_recency_score(c.pushed_days_ago)
            rel = calculate_relevance_score(query_terms, c.name, c.description, c.topics)
            lic_ok = 1.0 if is_commercially_viable(c.license_class) else 0.0
            return 0.50 * rel + 0.35 * rec + 0.15 * lic_ok

        deduped_a.sort(key=pre_score_a, reverse=True)
        deduped_b.sort(key=pre_score_b, reverse=True)

        quota_a = config.pre_score_quota_a
        quota_b = config.pre_score_quota_b

        # Transfer unused quota between buckets
        if len(deduped_a) < quota_a:
            quota_b += quota_a - len(deduped_a)
        elif len(deduped_b) < quota_b:
            quota_a += quota_b - len(deduped_b)

        shortlist = deduped_a[:quota_a] + deduped_b[:quota_b]

        # 5. Fetch Star Velocity and evaluate dormant_spike anomaly for shortlist concurrently
        async def _enrich_velocity(c: GitHubRepoCandidate):
            vel, anomaly = await self.get_star_velocity(
                c.owner, c.name, c.stars, c.created_days_ago
            )
            c.velocity = vel
            c.anomaly_warning = anomaly
            score, breakdown, conf = score_stage1(c, query_terms, commercial_use=commercial_use)
            c.score = score
            c.score_breakdown = breakdown
            c.confidence = conf

        await asyncio.gather(*[_enrich_velocity(c) for c in shortlist])

        # Rank by Stage 1 score
        shortlist.sort(key=lambda c: c.score, reverse=True)

        # 6. Stage 2: Fetch health metrics and PyPI adoption for top finalists concurrently
        finalists = shortlist[: config.finalists_count]

        async def _enrich_finalists(c: GitHubRepoCandidate):
            c.is_finalist = True
            health_task = self.get_repo_health(c.owner, c.name)
            pypi_task = pypi_client.get_repo_downloads(c.name)
            m_score, pypi_downloads = await asyncio.gather(health_task, pypi_task)
            c.maintenance_score = m_score
            c.pypi_downloads_30d = pypi_downloads

        await asyncio.gather(*[_enrich_finalists(c) for c in finalists])

        re_ranked_finalists = score_stage2_finalists(finalists)

        # Combine re-ranked finalists with remaining non-finalist shortlist
        remaining = shortlist[config.finalists_count :]
        final_list = re_ranked_finalists + remaining
        return final_list[:limit]


github_client = GitHubClient()

