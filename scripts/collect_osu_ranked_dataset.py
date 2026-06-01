#!/usr/bin/env python3
"""
Collect a reproducible osu! try dataset by sampling users from top country leaderboards.

Storage layout is JSONL-oriented to avoid directory spam:
- raw/sampled_users.jsonl
- raw/ranking_pages.jsonl
- raw/user_snapshots.jsonl
- raw/beatmaps.jsonl
- config.json
- state.json
- export_metadata.json
- osu_country_try_data_v1.csv
- profiling_summary.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

RULESET = "osu"
RANKING_PAGE_SIZE = 50
API_BASE_URL = "https://osu.ppy.sh/api/v2"
TOKEN_URL = "https://osu.ppy.sh/oauth/token"

DEFAULT_TOP_COUNTRY_COUNT = 100
DEFAULT_PLAYERS_PER_COUNTRY = 100
DEFAULT_COUNTRY_RANKING_MAX = 10_000
DEFAULT_COUNTRY_SAMPLE_MEAN_RATIO = 0.5
DEFAULT_COUNTRY_SAMPLE_STD_RATIO = 0.2

CSV_COLUMNS = [
    "row_id",
    "score_id",
    "user_id",
    "beatmap_id",
    "beatmapset_id",
    "ruleset",
    "collected_at",
    "score_created_at",
    "score_source",
    "seed_country_code",
    "seed_country_rank",
    "seed_country_player_rank",
    "seed_global_rank",
    "target_passed",
    "target_accuracy",
    "score_rank",
    "mods_raw",
    "observed_pp",
    "observed_max_combo",
    "count_300",
    "count_100",
    "count_50",
    "count_miss",
    "user_pp",
    "user_global_rank",
    "user_country_rank",
    "user_accuracy",
    "user_play_count",
    "user_play_time_sec",
    "user_total_hits",
    "user_maximum_combo",
    "beatmap_star_rating",
    "beatmap_bpm",
    "beatmap_ar",
    "beatmap_od",
    "beatmap_cs",
    "beatmap_hp",
    "beatmap_hit_length_sec",
    "beatmap_total_length_sec",
    "beatmap_count_circles",
    "beatmap_count_sliders",
    "beatmap_count_spinners",
    "beatmap_status",
    "beatmap_passcount",
    "beatmap_playcount",
]


def load_local_env() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for env_path in (repo_root / ".env.local", repo_root / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_mods(mods: Any) -> str:
    if mods is None:
        return ""
    if isinstance(mods, str):
        return mods
    if isinstance(mods, list):
        normalized: list[str] = []
        for mod in mods:
            if isinstance(mod, str):
                normalized.append(mod)
            elif isinstance(mod, dict):
                acronym = mod.get("acronym")
                if acronym:
                    normalized.append(str(acronym))
        return "".join(normalized)
    return str(mods)


def percent_0_to_100(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if 0.0 <= numeric <= 1.5:
        return round(numeric * 100.0, 4)
    return round(numeric, 4)


def score_statistics(score: dict[str, Any]) -> dict[str, Any]:
    stats = score.get("statistics") or {}
    return {
        "count_300": first_not_none(stats.get("count_300"), stats.get("great")),
        "count_100": first_not_none(stats.get("count_100"), stats.get("ok")),
        "count_50": first_not_none(stats.get("count_50"), stats.get("meh")),
        "count_miss": first_not_none(stats.get("count_miss"), stats.get("miss")),
    }


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    items: list[Any] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def log_progress(message: str) -> None:
    print(f"[{utc_now_iso()}] {message}", flush=True)


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def sampled_country_counts(sampled_users: list[dict[str, Any]]) -> dict[str, int]:
    return sorted_counter(Counter(str(item.get("country_code")) for item in sampled_users))


def processed_country_counts(sampled_users: list[dict[str, Any]], processed_user_ids: set[int]) -> dict[str, int]:
    return sorted_counter(
        Counter(str(item.get("country_code")) for item in sampled_users if int(item.get("user_id")) in processed_user_ids)
    )


def update_state(
    state_path: Path,
    *,
    phase: str | None = None,
    export_started_at: str | None = None,
    ranking_type: str | None = None,
    top_country_total_available: int | None = None,
    selected_country_count: int | None = None,
    ranking_pages_fetched: int | None = None,
    current_country_code: str | None = None,
    current_page: int | None = None,
    sampled_users: list[dict[str, Any]] | None = None,
    processed_user_ids: set[int] | None = None,
    cached_beatmap_ids: set[int] | None = None,
    referenced_beatmap_ids: set[int] | None = None,
    csv_row_count: int | None = None,
    note: str | None = None,
) -> None:
    state = read_json(state_path, {})
    if phase is not None:
        state["phase"] = phase
    if export_started_at is not None:
        state["export_started_at"] = export_started_at
    if ranking_type is not None:
        state["ranking_type"] = ranking_type
    if top_country_total_available is not None:
        state["top_country_total_available"] = top_country_total_available
    if selected_country_count is not None:
        state["selected_country_count"] = selected_country_count
    if ranking_pages_fetched is not None:
        state["ranking_pages_fetched"] = ranking_pages_fetched
    if current_country_code is not None:
        state["current_country_code"] = current_country_code
    if current_page is not None:
        state["current_page"] = current_page
    if sampled_users is not None:
        unique_sampled_user_ids = {int(item["user_id"]) for item in sampled_users}
        state["sampled_user_count"] = len(sampled_users)
        state["unique_sampled_user_count"] = len(unique_sampled_user_ids)
        state["total_sampled_user_count"] = len(sampled_users)
        state["sampled_country_counts"] = sampled_country_counts(sampled_users)
        if processed_user_ids is not None:
            state["processed_country_counts"] = processed_country_counts(sampled_users, processed_user_ids)
    if processed_user_ids is not None:
        state["processed_user_ids"] = sorted(processed_user_ids)
        state["processed_user_count"] = len(processed_user_ids)
        if sampled_users is not None:
            state["processed_country_counts"] = processed_country_counts(sampled_users, processed_user_ids)
    if cached_beatmap_ids is not None:
        state["cached_beatmap_ids"] = sorted(cached_beatmap_ids)
        state["cached_beatmap_count"] = len(cached_beatmap_ids)
    if referenced_beatmap_ids is not None:
        state["referenced_beatmap_count"] = len(referenced_beatmap_ids)
    if csv_row_count is not None:
        state["csv_row_count"] = csv_row_count
    if note is not None:
        state["note"] = note
    state["last_updated_at"] = utc_now_iso()
    write_json(state_path, state)


class OsuApiClient:
    def __init__(self, client_id: str, client_secret: str, timeout_seconds: float, request_delay_seconds: float) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout_seconds = timeout_seconds
        self._request_delay_seconds = request_delay_seconds
        self._session = requests.Session()
        self._access_token = self._fetch_access_token()

    def _fetch_access_token(self) -> str:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
            "scope": "public",
        }
        response = requests.post(TOKEN_URL, json=payload, timeout=self._timeout_seconds)
        response.raise_for_status()
        access_token = response.json().get("access_token")
        if not access_token:
            raise RuntimeError("osu! OAuth token response did not contain access_token")
        return access_token

    def get(self, path: str, params: Any = None) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }
        response = self._session.get(
            f"{API_BASE_URL}{path}",
            headers=headers,
            params=params or {},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        if self._request_delay_seconds > 0:
            time.sleep(self._request_delay_seconds)
        return response.json()

    def get_country_rankings(self, page: int) -> dict[str, Any]:
        return self.get(f"/rankings/{RULESET}/country", params={"page": page})

    def get_player_rankings(self, ranking_type: str, page: int, country_code: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page}
        if country_code:
            params["country"] = country_code
        return self.get(f"/rankings/{RULESET}/{ranking_type}", params=params)

    def get_user(self, user_id: int) -> dict[str, Any]:
        return self.get(f"/users/{user_id}/{RULESET}")

    def get_user_scores(self, user_id: int, score_type: str, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        params = {
            "mode": RULESET,
            "legacy_only": 0,
            "limit": limit,
        }
        if score_type == "recent":
            params["include_fails"] = 1
        response = self.get(f"/users/{user_id}/scores/{score_type}", params=params)
        if not isinstance(response, list):
            raise RuntimeError(f"Unexpected {score_type} score response for user {user_id}: {type(response)!r}")
        return response

    def get_beatmaps(self, beatmap_ids: Iterable[int], batch_size: int = 50) -> list[dict[str, Any]]:
        ids = [int(beatmap_id) for beatmap_id in beatmap_ids]
        if not ids:
            return []
        beatmaps: list[dict[str, Any]] = []
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            params = [("ids[]", beatmap_id) for beatmap_id in batch]
            response = self.get("/beatmaps", params=params)
            if isinstance(response, list):
                beatmaps.extend(response)
                continue
            if isinstance(response, dict):
                response_beatmaps = response.get("beatmaps")
                if isinstance(response_beatmaps, list):
                    beatmaps.extend(response_beatmaps)
                    continue
            raise RuntimeError(f"Unexpected beatmaps response: {type(response)!r}")
        return beatmaps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for the collection run. Defaults to data/raw/osu_country_try_data_<timestamp>/",
    )
    parser.add_argument(
        "--ranking-type",
        default="performance",
        help="osu! ranking type used for user seeding.",
    )
    parser.add_argument(
        "--top-country-count",
        type=int,
        default=DEFAULT_TOP_COUNTRY_COUNT,
        help="How many top countries to seed from the country rankings endpoint.",
    )
    parser.add_argument(
        "--players-per-country",
        type=int,
        default=DEFAULT_PLAYERS_PER_COUNTRY,
        help="How many players to sample from each selected country ranking.",
    )
    parser.add_argument(
        "--country-ranking-max",
        type=int,
        default=DEFAULT_COUNTRY_RANKING_MAX,
        help="Maximum local rank within each country to sample from.",
    )
    parser.add_argument(
        "--country-sample-mean-ratio",
        type=float,
        default=DEFAULT_COUNTRY_SAMPLE_MEAN_RATIO,
        help="Mean position for truncated-normal country-rank sampling, expressed as a 0-1 ratio of local ranking depth.",
    )
    parser.add_argument(
        "--country-sample-std-ratio",
        type=float,
        default=DEFAULT_COUNTRY_SAMPLE_STD_RATIO,
        help="Standard deviation for truncated-normal country-rank sampling, expressed as a 0-1 ratio of local ranking depth.",
    )
    parser.add_argument(
        "--recent-scores-per-user",
        type=int,
        default=30,
        help="Number of recent scores to fetch per sampled user.",
    )
    parser.add_argument(
        "--best-scores-per-user",
        type=int,
        default=20,
        help="Number of best scores to fetch per sampled user.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Seed used for reproducible user sampling within each country ranking.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=0.05,
        help="Delay between API requests.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def build_output_dir(output_dir_arg: str | None) -> Path:
    if output_dir_arg:
        return Path(output_dir_arg)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data") / "raw" / f"osu_country_try_data_{timestamp}"


def country_rank_to_page(country_player_rank: int) -> int:
    return math.ceil(country_player_rank / RANKING_PAGE_SIZE)


def sample_unique_country_ranks(
    *,
    max_rank: int,
    sample_size: int,
    rng: random.Random,
    mean_ratio: float,
    std_ratio: float,
) -> list[int]:
    if max_rank < sample_size:
        raise RuntimeError(f"Cannot sample {sample_size} unique local ranks from only {max_rank} available entries")

    mean = 1.0 + (max_rank - 1) * mean_ratio
    std_dev = max(1.0, max_rank * std_ratio)
    selected: set[int] = set()
    attempts = 0
    max_attempts = sample_size * 500

    while len(selected) < sample_size and attempts < max_attempts:
        attempts += 1
        candidate = int(round(rng.gauss(mean, std_dev)))
        candidate = min(max(candidate, 1), max_rank)
        selected.add(candidate)

    if len(selected) < sample_size:
        remaining = [rank for rank in range(1, max_rank + 1) if rank not in selected]
        selected.update(rng.sample(remaining, sample_size - len(selected)))

    return sorted(selected)


def manifest_validation_errors(
    sampled_users: list[dict[str, Any]],
    *,
    players_per_country: int,
    top_country_count: int,
) -> list[str]:
    if not sampled_users:
        return ["sampled_users.jsonl is empty"]

    errors: list[str] = []
    counts_by_country: Counter[str] = Counter()
    seen_user_ids: set[int] = set()
    seen_country_ranks: set[int] = set()

    for sampled_user in sampled_users:
        country_code = str(sampled_user.get("country_code"))
        user_id_raw = sampled_user.get("user_id")
        country_rank_raw = sampled_user.get("country_rank")
        country_player_rank_raw = sampled_user.get("country_player_rank")
        global_rank_raw = sampled_user.get("seed_global_rank")

        if not country_code:
            errors.append("Manifest row is missing country_code")
            continue
        if user_id_raw is None:
            errors.append(f"Manifest row is missing user_id for country {country_code}")
            continue
        user_id = int(user_id_raw)
        if user_id in seen_user_ids:
            errors.append(f"Duplicate sampled user_id detected: {user_id}")
        seen_user_ids.add(user_id)

        if country_rank_raw is None:
            errors.append(f"Manifest row is missing country_rank for country {country_code}")
        else:
            seen_country_ranks.add(int(country_rank_raw))

        if country_player_rank_raw is None:
            errors.append(f"Manifest row is missing country_player_rank for user {user_id}")
        elif int(country_player_rank_raw) < 1:
            errors.append(f"Invalid country_player_rank for user {user_id}: {country_player_rank_raw}")

        if global_rank_raw is None:
            errors.append(f"Manifest row is missing seed_global_rank for user {user_id}")

        counts_by_country[country_code] += 1

    if len(counts_by_country) != top_country_count:
        errors.append(f"Manifest has {len(counts_by_country)} countries, expected {top_country_count}")
    for country_code, count in sorted(counts_by_country.items()):
        if count != players_per_country:
            errors.append(f"Country {country_code} has {count} sampled users, expected {players_per_country}")
    if len(seen_country_ranks) != top_country_count:
        errors.append(
            f"Manifest has {len(seen_country_ranks)} distinct country ranks, expected {top_country_count}"
        )
    return errors


def fetch_country_ranking_page(
    client: OsuApiClient,
    page: int,
    ranking_pages_path: Path,
    page_cache: dict[tuple[str, int], dict[str, Any]],
    fetched_pages: set[tuple[str, int]],
) -> dict[str, Any]:
    cache_key = ("country", page)
    cached = page_cache.get(cache_key)
    if cached is not None:
        return cached

    response = client.get_country_rankings(page)
    page_cache[cache_key] = response
    fetched_pages.add(cache_key)
    append_jsonl(
        ranking_pages_path,
        {
            "request_kind": "country_rankings",
            "page": page,
            "collected_at": utc_now_iso(),
            "response": response,
        },
    )
    return response


def fetch_country_player_page(
    client: OsuApiClient,
    *,
    ranking_type: str,
    country_code: str,
    page: int,
    ranking_pages_path: Path,
    page_cache: dict[tuple[str, int], dict[str, Any]],
    fetched_pages: set[tuple[str, int]],
) -> dict[str, Any]:
    cache_key = (country_code, page)
    cached = page_cache.get(cache_key)
    if cached is not None:
        return cached

    response = client.get_player_rankings(ranking_type, page, country_code=country_code)
    page_cache[cache_key] = response
    fetched_pages.add(cache_key)
    append_jsonl(
        ranking_pages_path,
        {
            "request_kind": "player_rankings",
            "ranking_type": ranking_type,
            "country_code": country_code,
            "page": page,
            "collected_at": utc_now_iso(),
            "response": response,
        },
    )
    return response


def select_top_countries(
    client: OsuApiClient,
    *,
    top_country_count: int,
    ranking_pages_path: Path,
    page_cache: dict[tuple[str, int], dict[str, Any]],
    fetched_pages: set[tuple[str, int]],
    state_path: Path,
) -> tuple[list[dict[str, Any]], int]:
    selected_countries: list[dict[str, Any]] = []
    page = 1
    total_available = 0

    while len(selected_countries) < top_country_count:
        response = fetch_country_ranking_page(client, page, ranking_pages_path, page_cache, fetched_pages)
        total_available = int(response.get("total") or 0)
        ranking_entries = response.get("ranking") or []
        if not ranking_entries:
            break

        update_state(
            state_path,
            phase="selecting_countries",
            top_country_total_available=total_available,
            selected_country_count=len(selected_countries),
            ranking_pages_fetched=len(fetched_pages),
            current_page=page,
            note="Selecting top countries from the country leaderboard",
        )

        for index_on_page, entry in enumerate(ranking_entries):
            if len(selected_countries) >= top_country_count:
                break
            country_rank = (page - 1) * RANKING_PAGE_SIZE + index_on_page + 1
            country_code = entry.get("code")
            if not country_code:
                continue
            selected_countries.append(
                {
                    "country_code": str(country_code),
                    "country_rank": country_rank,
                    "active_users": entry.get("active_users"),
                    "play_count": entry.get("play_count"),
                    "ranked_score": entry.get("ranked_score"),
                }
            )

        next_page = ((response.get("cursor") or {}).get("page")) if isinstance(response, dict) else None
        if next_page is None or int(next_page) <= page:
            break
        page = int(next_page)

    if total_available <= 0:
        raise RuntimeError("osu! country rankings response did not expose a usable total country count")
    if top_country_count > total_available:
        raise RuntimeError(
            f"Requested top_country_count={top_country_count}, but the API exposes only {total_available} countries"
        )
    if len(selected_countries) < top_country_count:
        raise RuntimeError(
            f"Collected only {len(selected_countries)} top countries, expected {top_country_count}"
        )
    return selected_countries, total_available


def sample_country_users(
    client: OsuApiClient,
    *,
    country: dict[str, Any],
    ranking_type: str,
    players_per_country: int,
    country_ranking_max: int,
    mean_ratio: float,
    std_ratio: float,
    random_seed: int,
    ranking_pages_path: Path,
    page_cache: dict[tuple[str, int], dict[str, Any]],
    fetched_pages: set[tuple[str, int]],
    state_path: Path,
    top_country_total_available: int,
    selected_country_count: int,
) -> list[dict[str, Any]]:
    country_code = str(country["country_code"])
    first_page_response = fetch_country_player_page(
        client,
        ranking_type=ranking_type,
        country_code=country_code,
        page=1,
        ranking_pages_path=ranking_pages_path,
        page_cache=page_cache,
        fetched_pages=fetched_pages,
    )
    country_total_available = int(first_page_response.get("total") or 0)
    effective_max_rank = min(country_ranking_max, country_total_available)
    if effective_max_rank < players_per_country:
        raise RuntimeError(
            f"Country {country_code} exposes only {effective_max_rank} local ranks, "
            f"but players_per_country requires {players_per_country}"
        )

    rng = random.Random(random_seed + int(country["country_rank"]))
    sampled_local_ranks = sample_unique_country_ranks(
        max_rank=effective_max_rank,
        sample_size=players_per_country,
        rng=rng,
        mean_ratio=mean_ratio,
        std_ratio=std_ratio,
    )
    target_ranks = set(sampled_local_ranks)
    pages_to_fetch = sorted({country_rank_to_page(local_rank) for local_rank in sampled_local_ranks} | {1})
    selected_users: dict[int, dict[str, Any]] = {}

    for page in pages_to_fetch:
        response = first_page_response if page == 1 else fetch_country_player_page(
            client,
            ranking_type=ranking_type,
            country_code=country_code,
            page=page,
            ranking_pages_path=ranking_pages_path,
            page_cache=page_cache,
            fetched_pages=fetched_pages,
        )
        update_state(
            state_path,
            phase="sampling_manifest",
            top_country_total_available=top_country_total_available,
            selected_country_count=selected_country_count,
            ranking_pages_fetched=len(fetched_pages),
            current_country_code=country_code,
            current_page=page,
            note=f"Sampling users for country {country_code}",
        )

        ranking_entries = response.get("ranking") or []
        for index_on_page, entry in enumerate(ranking_entries):
            local_rank = (page - 1) * RANKING_PAGE_SIZE + index_on_page + 1
            if local_rank not in target_ranks:
                continue
            user = entry.get("user") or {}
            user_id = user.get("id")
            global_rank = entry.get("global_rank")
            if user_id is None or global_rank is None:
                continue
            selected_users[local_rank] = {
                "user_id": int(user_id),
                "country_code": country_code,
                "country_rank": int(country["country_rank"]),
                "country_player_rank": local_rank,
                "seed_global_rank": int(global_rank),
                "ranking_page": page,
            }

    missing_ranks = sorted(target_ranks - set(selected_users))
    if missing_ranks:
        raise RuntimeError(
            f"Country {country_code} is missing sampled local ranks after page fetch: {missing_ranks[:10]}"
        )

    return [selected_users[local_rank] for local_rank in sorted(selected_users)]


def build_sampling_manifest(
    client: OsuApiClient,
    *,
    ranking_type: str,
    top_country_count: int,
    players_per_country: int,
    country_ranking_max: int,
    mean_ratio: float,
    std_ratio: float,
    random_seed: int,
    raw_dir: Path,
    state_path: Path,
) -> list[dict[str, Any]]:
    sampled_users_path = raw_dir / "sampled_users.jsonl"
    ranking_pages_path = raw_dir / "ranking_pages.jsonl"
    if sampled_users_path.exists():
        sampled_users = read_jsonl(sampled_users_path)
        errors = manifest_validation_errors(
            sampled_users,
            players_per_country=players_per_country,
            top_country_count=top_country_count,
        )
        if errors:
            joined = "; ".join(errors[:5])
            raise RuntimeError(
                "Existing sampled_users.jsonl is invalid. "
                f"{joined}. Remove the run directory or use a new --output-dir."
            )
        update_state(
            state_path,
            phase="sampling_manifest_ready",
            sampled_users=sampled_users,
            selected_country_count=len({item['country_code'] for item in sampled_users}),
            note="Loaded existing valid sampled user manifest",
        )
        return sampled_users

    page_cache: dict[tuple[str, int], dict[str, Any]] = {}
    fetched_pages: set[tuple[str, int]] = set()
    selected_countries, top_country_total_available = select_top_countries(
        client,
        top_country_count=top_country_count,
        ranking_pages_path=ranking_pages_path,
        page_cache=page_cache,
        fetched_pages=fetched_pages,
        state_path=state_path,
    )

    sampled_users: list[dict[str, Any]] = []
    for country in selected_countries:
        country_users = sample_country_users(
            client,
            country=country,
            ranking_type=ranking_type,
            players_per_country=players_per_country,
            country_ranking_max=country_ranking_max,
            mean_ratio=mean_ratio,
            std_ratio=std_ratio,
            random_seed=random_seed,
            ranking_pages_path=ranking_pages_path,
            page_cache=page_cache,
            fetched_pages=fetched_pages,
            state_path=state_path,
            top_country_total_available=top_country_total_available,
            selected_country_count=len(selected_countries),
        )
        sampled_users.extend(country_users)
        update_state(
            state_path,
            phase="sampling_manifest",
            top_country_total_available=top_country_total_available,
            selected_country_count=len(selected_countries),
            ranking_pages_fetched=len(fetched_pages),
            sampled_users=sampled_users,
            current_country_code=str(country["country_code"]),
            note=f"Sampled {len(sampled_users)} users so far",
        )
        log_progress(
            f"Sampled country {country['country_code']}: {players_per_country} users from top {country_ranking_max} local ranks"
        )

    sampled_users = sorted(
        sampled_users,
        key=lambda item: (
            int(item["country_rank"]),
            str(item["country_code"]),
            int(item["country_player_rank"]),
            int(item["user_id"]),
        ),
    )
    errors = manifest_validation_errors(
        sampled_users,
        players_per_country=players_per_country,
        top_country_count=top_country_count,
    )
    if errors:
        raise RuntimeError(f"Generated manifest failed validation: {'; '.join(errors[:5])}")
    for sampled_user in sampled_users:
        append_jsonl(sampled_users_path, sampled_user)
    update_state(
        state_path,
        phase="sampling_manifest_ready",
        top_country_total_available=top_country_total_available,
        selected_country_count=len(selected_countries),
        ranking_pages_fetched=len(fetched_pages),
        sampled_users=sampled_users,
        note="Finished sampled user manifest",
    )
    return sampled_users


def merge_scores(recent_scores: list[dict[str, Any]], best_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for score_source, source_scores in (("recent", recent_scores), ("best", best_scores)):
        for score in source_scores:
            score_id = score.get("id")
            dedupe_key = score_id if score_id is not None else (
                score.get("user_id"),
                score.get("beatmap_id"),
                score.get("created_at"),
                score_source,
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            score_copy = dict(score)
            score_copy["_score_source"] = score_source
            merged.append(score_copy)
    return merged


def collect_user_snapshots(
    client: OsuApiClient,
    sampled_users: list[dict[str, Any]],
    raw_dir: Path,
    recent_scores_per_user: int,
    best_scores_per_user: int,
    state_path: Path,
) -> None:
    user_snapshots_path = raw_dir / "user_snapshots.jsonl"
    state = read_json(state_path, {})
    processed_user_ids = set(state.get("processed_user_ids", []))
    total_sampled_users = len(sampled_users)

    update_state(
        state_path,
        phase="collecting_user_snapshots",
        sampled_users=sampled_users,
        processed_user_ids=processed_user_ids,
        note="Collecting user profiles and score snapshots",
    )

    for index, sampled_user in enumerate(sampled_users, start=1):
        user_id = int(sampled_user["user_id"])
        if user_id in processed_user_ids:
            continue

        profile = client.get_user(user_id)
        recent_scores = client.get_user_scores(user_id, "recent", recent_scores_per_user)
        best_scores = client.get_user_scores(user_id, "best", best_scores_per_user)
        merged_scores = merge_scores(recent_scores, best_scores)

        bundle = {
            "user_id": user_id,
            "sampled_user": sampled_user,
            "collected_at": utc_now_iso(),
            "profile": profile,
            "recent_scores": recent_scores,
            "best_scores": best_scores,
            "merged_scores": merged_scores,
        }
        append_jsonl(user_snapshots_path, bundle)

        processed_user_ids.add(user_id)
        update_state(
            state_path,
            phase="collecting_user_snapshots",
            sampled_users=sampled_users,
            processed_user_ids=processed_user_ids,
            current_country_code=str(sampled_user["country_code"]),
            note=f"Processed user {len(processed_user_ids)} / {total_sampled_users}",
        )
        if len(processed_user_ids) == 1 or len(processed_user_ids) % 10 == 0 or index == total_sampled_users:
            log_progress(f"Collected user snapshots: {len(processed_user_ids)} / {total_sampled_users}")


def collect_missing_beatmaps(
    client: OsuApiClient,
    raw_dir: Path,
    state_path: Path,
    sampled_users: list[dict[str, Any]],
) -> None:
    user_snapshots_path = raw_dir / "user_snapshots.jsonl"
    beatmaps_path = raw_dir / "beatmaps.jsonl"

    referenced_beatmap_ids: set[int] = set()
    for bundle in read_jsonl(user_snapshots_path):
        for score in bundle.get("merged_scores", []):
            beatmap_id = first_not_none(score.get("beatmap_id"), (score.get("beatmap") or {}).get("id"))
            if beatmap_id is not None:
                referenced_beatmap_ids.add(int(beatmap_id))

    state = read_json(state_path, {})
    cached_beatmap_ids = set(state.get("cached_beatmap_ids", []))
    if not cached_beatmap_ids and beatmaps_path.exists():
        cached_beatmap_ids = {
            int(beatmap["id"])
            for beatmap in read_jsonl(beatmaps_path)
            if isinstance(beatmap, dict) and beatmap.get("id") is not None
        }

    update_state(
        state_path,
        phase="collecting_beatmaps",
        sampled_users=sampled_users,
        cached_beatmap_ids=cached_beatmap_ids,
        referenced_beatmap_ids=referenced_beatmap_ids,
        note="Collecting beatmap metadata for referenced scores",
    )

    missing_ids = sorted(referenced_beatmap_ids - cached_beatmap_ids)
    if not missing_ids:
        log_progress("Beatmap cache already complete for all referenced beatmaps")
        return

    log_progress(f"Collecting {len(missing_ids)} missing beatmaps")
    beatmaps = client.get_beatmaps(missing_ids)
    for beatmap in beatmaps:
        beatmap_id = beatmap.get("id")
        if beatmap_id is None:
            continue
        append_jsonl(beatmaps_path, beatmap)
        cached_beatmap_ids.add(int(beatmap_id))

    update_state(
        state_path,
        phase="collecting_beatmaps",
        sampled_users=sampled_users,
        cached_beatmap_ids=cached_beatmap_ids,
        referenced_beatmap_ids=referenced_beatmap_ids,
        note=f"Beatmap cache contains {len(cached_beatmap_ids)} entries",
    )
    log_progress(f"Beatmap cache ready: {len(cached_beatmap_ids)} beatmaps")


def load_beatmap_cache(raw_dir: Path) -> dict[int, dict[str, Any]]:
    cache: dict[int, dict[str, Any]] = {}
    for beatmap in read_jsonl(raw_dir / "beatmaps.jsonl"):
        beatmap_id = beatmap.get("id")
        if beatmap_id is not None:
            cache[int(beatmap_id)] = beatmap
    return cache


def flatten_row(
    score: dict[str, Any],
    profile: dict[str, Any],
    beatmap: dict[str, Any] | None,
    sampled_user: dict[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    beatmap = beatmap or score.get("beatmap") or {}
    beatmapset = score.get("beatmapset") or {}
    user_stats = profile.get("statistics") or {}
    score_stats = score_statistics(score)
    score_created_at = first_not_none(score.get("created_at"), score.get("ended_at"))
    beatmap_id = first_not_none(score.get("beatmap_id"), beatmap.get("id"))
    score_id = score.get("id")

    return {
        "row_id": str(score_id) if score_id is not None else f"{profile.get('id')}_{beatmap_id}_{score_created_at}_{score.get('_score_source', 'recent')}",
        "score_id": score_id,
        "user_id": first_not_none(score.get("user_id"), profile.get("id")),
        "beatmap_id": beatmap_id,
        "beatmapset_id": first_not_none(beatmap.get("beatmapset_id"), beatmapset.get("id")),
        "ruleset": RULESET,
        "collected_at": collected_at,
        "score_created_at": score_created_at,
        "score_source": score.get("_score_source", "recent"),
        "seed_country_code": sampled_user.get("country_code"),
        "seed_country_rank": sampled_user.get("country_rank"),
        "seed_country_player_rank": sampled_user.get("country_player_rank"),
        "seed_global_rank": sampled_user.get("seed_global_rank"),
        "target_passed": score.get("passed"),
        "target_accuracy": percent_0_to_100(score.get("accuracy")),
        "score_rank": score.get("rank"),
        "mods_raw": normalize_mods(score.get("mods")),
        "observed_pp": score.get("pp"),
        "observed_max_combo": first_not_none(score.get("max_combo"), score.get("maximum_statistics", {}).get("max_combo")),
        "count_300": score_stats["count_300"],
        "count_100": score_stats["count_100"],
        "count_50": score_stats["count_50"],
        "count_miss": score_stats["count_miss"],
        "user_pp": user_stats.get("pp"),
        "user_global_rank": user_stats.get("global_rank"),
        "user_country_rank": user_stats.get("country_rank"),
        "user_accuracy": percent_0_to_100(user_stats.get("hit_accuracy")),
        "user_play_count": user_stats.get("play_count"),
        "user_play_time_sec": user_stats.get("play_time"),
        "user_total_hits": user_stats.get("total_hits"),
        "user_maximum_combo": user_stats.get("maximum_combo"),
        "beatmap_star_rating": beatmap.get("difficulty_rating"),
        "beatmap_bpm": beatmap.get("bpm"),
        "beatmap_ar": beatmap.get("ar"),
        "beatmap_od": beatmap.get("accuracy"),
        "beatmap_cs": beatmap.get("cs"),
        "beatmap_hp": beatmap.get("drain"),
        "beatmap_hit_length_sec": beatmap.get("hit_length"),
        "beatmap_total_length_sec": beatmap.get("total_length"),
        "beatmap_count_circles": beatmap.get("count_circles"),
        "beatmap_count_sliders": beatmap.get("count_sliders"),
        "beatmap_count_spinners": beatmap.get("count_spinners"),
        "beatmap_status": beatmap.get("status"),
        "beatmap_passcount": beatmap.get("passcount"),
        "beatmap_playcount": beatmap.get("playcount"),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_rows(raw_dir: Path) -> list[dict[str, Any]]:
    beatmaps_by_id = load_beatmap_cache(raw_dir)
    rows: list[dict[str, Any]] = []
    for bundle in read_jsonl(raw_dir / "user_snapshots.jsonl"):
        profile = bundle.get("profile") or {}
        sampled_user = bundle.get("sampled_user") or {}
        collected_at = bundle.get("collected_at") or utc_now_iso()
        for score in bundle.get("merged_scores", []):
            beatmap_id = first_not_none(score.get("beatmap_id"), (score.get("beatmap") or {}).get("id"))
            beatmap = beatmaps_by_id.get(int(beatmap_id)) if beatmap_id is not None else None
            rows.append(flatten_row(score, profile, beatmap, sampled_user, collected_at))
    return rows


def build_profile_summary(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    csv_name: str,
    sampled_users: list[dict[str, Any]],
    state: dict[str, Any],
) -> str:
    total_rows = len(rows)
    unique_users = len({row["user_id"] for row in rows})
    unique_beatmaps = len({row["beatmap_id"] for row in rows})
    passed = sum(str(row["target_passed"]).lower() == "true" for row in rows)
    failed = total_rows - passed
    pass_rate = (passed / total_rows) if total_rows else 0.0

    def numeric_values(column: str) -> list[float]:
        values: list[float] = []
        for row in rows:
            raw = row.get(column)
            if raw in ("", None):
                continue
            values.append(float(raw))
        return values

    def stat_block(column: str) -> list[str]:
        values = numeric_values(column)
        if not values:
            return [f"- `{column}`: no values"]
        values_sorted = sorted(values)
        mid = len(values_sorted) // 2
        median = values_sorted[mid] if len(values_sorted) % 2 else (values_sorted[mid - 1] + values_sorted[mid]) / 2
        mean = sum(values_sorted) / len(values_sorted)
        return [
            f"- `{column}`",
            f"  - mean: `{mean:.4f}`",
            f"  - median: `{median:.4f}`",
            f"  - min: `{min(values_sorted):.4f}`",
            f"  - max: `{max(values_sorted):.4f}`",
        ]

    source_counts = Counter(row["score_source"] for row in rows)
    country_row_counts = Counter(str(row["seed_country_code"]) for row in rows)
    mod_counts = Counter((row["mods_raw"] or "NM") for row in rows)
    collected_values = sorted({row["collected_at"] for row in rows if row.get("collected_at")})
    sampled_counts = sampled_country_counts(sampled_users)
    processed_counts = state.get("processed_country_counts") or {}

    lines = [
        "# Profiling Summary",
        "",
        f"Dataset: `{csv_name}`",
        "",
        "## Collection Metadata",
        "",
        "- Source: official osu! API v2",
        f"- Ruleset: `{RULESET}`",
        f"- Export started at: `{metadata['export_started_at']}`",
        f"- Export finished at: `{metadata['export_finished_at']}`",
        f"- Export duration seconds: `{metadata['export_duration_seconds']}`",
        f"- Earliest row collected_at: `{collected_values[0] if collected_values else ''}`",
        f"- Latest row collected_at: `{collected_values[-1] if collected_values else ''}`",
        f"- Ranking type: `{metadata['ranking_type']}`",
        f"- Random seed: `{metadata['random_seed']}`",
        f"- Top country count: `{metadata['top_country_count']}`",
        f"- Players per country: `{metadata['players_per_country']}`",
        f"- Country ranking max: `{metadata['country_ranking_max']}`",
        f"- Country sample mean ratio: `{metadata['country_sample_mean_ratio']}`",
        f"- Country sample std ratio: `{metadata['country_sample_std_ratio']}`",
        f"- Country leaderboard size: `{metadata['top_country_total_available']}`",
        f"- Recent scores per user: `{metadata['recent_scores_per_user']}`",
        f"- Best scores per user: `{metadata['best_scores_per_user']}`",
        "",
        "## Size",
        "",
        f"- Rows: `{total_rows}`",
        f"- Unique users: `{unique_users}`",
        f"- Unique beatmaps: `{unique_beatmaps}`",
        f"- Sampled users requested: `{metadata['sampled_user_count']}`",
        f"- Unique sampled users: `{metadata['unique_sampled_user_count']}`",
        f"- Processed users: `{metadata['processed_user_count']}`",
        "",
        "## Sampled Users Per Country",
        "",
        *[f"- `{country}`: `{count}`" for country, count in sampled_counts.items()],
        "",
        "## Processed Users Per Country",
        "",
        *[f"- `{country}`: `{count}`" for country, count in sorted(processed_counts.items())],
        "",
        "## Target Distribution",
        "",
        f"- Passed: `{passed}`",
        f"- Failed: `{failed}`",
        f"- Pass rate: `{pass_rate:.4%}`",
        "",
        "## Numeric Summary",
        "",
        *stat_block("target_accuracy"),
        *stat_block("beatmap_star_rating"),
        *stat_block("beatmap_bpm"),
        "",
        "## Score Sources",
        "",
        *[f"- `{source}`: `{count}`" for source, count in source_counts.most_common()],
        "",
        "## Rows Per Country",
        "",
        *[f"- `{country}`: `{count}`" for country, count in sorted(country_row_counts.items())],
        "",
        "## Top Mods",
        "",
        *[f"- `{mod}`: `{count}`" for mod, count in mod_counts.most_common(10)],
        "",
        "## Observations",
        "",
        "- This export uses deterministic country-local rank sampling, so re-running with the same config should preserve the sampled user pool.",
        "- `seed_country_player_rank` is the sampled local rank inside the country leaderboard, while `seed_global_rank` keeps the player's global position at sampling time.",
        "- The public country player rankings endpoint currently exposes only the top `10000` users per country, so `country_ranking_max` must stay within that coverage.",
        "- JSONL storage keeps raw data append-friendly and much easier to inspect than large directories of tiny JSON files.",
        "- `best` score rows improve positive-label coverage, but source mix should be tracked during training.",
        "- Resume safety comes from append-only user snapshots, beatmap cache reuse, and state.json checkpoints.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    load_local_env()

    if args.top_country_count < 1:
        raise RuntimeError("top_country_count must be >= 1")
    if args.players_per_country < 1:
        raise RuntimeError("players_per_country must be >= 1")
    if args.country_ranking_max < 1:
        raise RuntimeError("country_ranking_max must be >= 1")
    if not 0.0 <= args.country_sample_mean_ratio <= 1.0:
        raise RuntimeError("country_sample_mean_ratio must be between 0 and 1")
    if args.country_sample_std_ratio <= 0.0:
        raise RuntimeError("country_sample_std_ratio must be > 0")

    output_dir = build_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "ruleset": RULESET,
        "ranking_type": args.ranking_type,
        "top_country_count": args.top_country_count,
        "players_per_country": args.players_per_country,
        "country_ranking_max": args.country_ranking_max,
        "country_sample_mean_ratio": args.country_sample_mean_ratio,
        "country_sample_std_ratio": args.country_sample_std_ratio,
        "recent_scores_per_user": args.recent_scores_per_user,
        "best_scores_per_user": args.best_scores_per_user,
        "random_seed": args.random_seed,
    }
    config_path = output_dir / "config.json"
    if config_path.exists():
        existing = read_json(config_path, {})
        if existing != config:
            raise RuntimeError(f"Existing config.json does not match requested config in {output_dir}")
    else:
        write_json(config_path, config)

    client_id = os.getenv("OSU_CLIENT_ID")
    client_secret = os.getenv("OSU_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("Missing OSU_CLIENT_ID / OSU_CLIENT_SECRET in environment or .env.local")

    export_started_at = utc_now_iso()
    state_path = output_dir / "state.json"
    update_state(
        state_path,
        phase="initializing",
        export_started_at=export_started_at,
        ranking_type=args.ranking_type,
        note="Initializing osu! country-seeded try dataset collection",
    )
    client = OsuApiClient(
        client_id=client_id,
        client_secret=client_secret,
        timeout_seconds=args.timeout_seconds,
        request_delay_seconds=args.request_delay_seconds,
    )
    log_progress(f"Collector started in {output_dir.as_posix()}")

    sampled_users = build_sampling_manifest(
        client,
        ranking_type=args.ranking_type,
        top_country_count=args.top_country_count,
        players_per_country=args.players_per_country,
        country_ranking_max=args.country_ranking_max,
        mean_ratio=args.country_sample_mean_ratio,
        std_ratio=args.country_sample_std_ratio,
        random_seed=args.random_seed,
        raw_dir=raw_dir,
        state_path=state_path,
    )
    collect_user_snapshots(client, sampled_users, raw_dir, args.recent_scores_per_user, args.best_scores_per_user, state_path)
    collect_missing_beatmaps(client, raw_dir, state_path, sampled_users)

    update_state(state_path, phase="building_rows", sampled_users=sampled_users, note="Flattening rows into CSV")
    rows = build_rows(raw_dir)
    csv_name = "osu_country_try_data_v1.csv"
    csv_path = output_dir / csv_name
    write_csv(csv_path, rows)
    log_progress(f"Wrote CSV with {len(rows)} rows")

    export_finished_at = utc_now_iso()
    export_duration_seconds = round(
        datetime.fromisoformat(export_finished_at.replace("Z", "+00:00")).timestamp()
        - datetime.fromisoformat(export_started_at.replace("Z", "+00:00")).timestamp(),
        3,
    )
    final_state = read_json(state_path, {})
    metadata = {
        "export_started_at": export_started_at,
        "export_finished_at": export_finished_at,
        "export_duration_seconds": export_duration_seconds,
        "ranking_type": args.ranking_type,
        "random_seed": args.random_seed,
        "top_country_count": args.top_country_count,
        "players_per_country": args.players_per_country,
        "country_ranking_max": args.country_ranking_max,
        "country_sample_mean_ratio": args.country_sample_mean_ratio,
        "country_sample_std_ratio": args.country_sample_std_ratio,
        "top_country_total_available": final_state.get("top_country_total_available"),
        "recent_scores_per_user": args.recent_scores_per_user,
        "best_scores_per_user": args.best_scores_per_user,
        "sampled_user_count": len(sampled_users),
        "unique_sampled_user_count": len({int(item["user_id"]) for item in sampled_users}),
        "processed_user_count": final_state.get("processed_user_count", 0),
        "exported_row_count": len(rows),
    }
    write_json(output_dir / "export_metadata.json", metadata)
    update_state(
        state_path,
        phase="done",
        sampled_users=sampled_users,
        csv_row_count=len(rows),
        note="Collection finished successfully",
    )
    final_state = read_json(state_path, {})
    (output_dir / "profiling_summary.md").write_text(
        build_profile_summary(rows, metadata, csv_name, sampled_users, final_state),
        encoding="utf-8",
    )

    print(f"Wrote {len(rows)} rows to {csv_path.as_posix()}")
    print(f"Run directory: {output_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
