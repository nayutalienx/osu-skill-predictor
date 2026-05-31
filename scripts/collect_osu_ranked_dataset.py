#!/usr/bin/env python3
"""
Collect a larger, reproducible osu! dataset by sampling users from ranking bands.

Storage layout is JSONL-oriented to avoid directory spam:
- raw/sampled_users.jsonl
- raw/ranking_pages.jsonl
- raw/user_snapshots.jsonl
- raw/beatmaps.jsonl
- config.json
- state.json
- export_metadata.json
- osu_ranked_attempts_v1.csv
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

DEFAULT_BAND_SPEC = ",".join(
    [
        "1-1000:100",
        "1001-10000:100",
        "10001-20000:100",
        "20001-30000:100",
        "30001-40000:100",
        "40001-50000:100",
        "50001-60000:100",
        "60001-70000:100",
        "70001-80000:100",
        "80001-90000:100",
        "90001-100000:100",
    ]
)

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
    "seed_band",
    "seed_user_rank",
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

    def get_rankings(self, ranking_type: str, page: int) -> dict[str, Any]:
        return self.get(f"/rankings/{RULESET}/{ranking_type}", params={"page": page})

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
        help="Output directory for the collection run. Defaults to data/raw/osu_ranked_attempts_<timestamp>/",
    )
    parser.add_argument(
        "--band-spec",
        default=DEFAULT_BAND_SPEC,
        help='Comma-separated band spec, e.g. "1-1000:100,1001-10000:100". Format is start-end:sample_size.',
    )
    parser.add_argument(
        "--ranking-type",
        default="performance",
        help="osu! ranking type used for user seeding.",
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
        help="Seed used for reproducible user sampling within ranking bands.",
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
    return Path("data") / "raw" / f"osu_ranked_attempts_{timestamp}"


def parse_band_spec(spec: str) -> list[dict[str, Any]]:
    bands: list[dict[str, Any]] = []
    for index, raw_band in enumerate(spec.split(","), start=1):
        token = raw_band.strip()
        if not token:
            continue
        try:
            range_part, sample_part = token.split(":", 1)
            start_str, end_str = range_part.split("-", 1)
            rank_start = int(start_str)
            rank_end = int(end_str)
            sample_size = int(sample_part)
        except ValueError as exc:
            raise ValueError(f"Invalid band spec token: {token!r}") from exc
        if rank_start < 1 or rank_end < rank_start or sample_size < 1:
            raise ValueError(f"Invalid band values: {token!r}")
        bands.append(
            {
                "index": index,
                "label": f"{rank_start}-{rank_end}",
                "rank_start": rank_start,
                "rank_end": rank_end,
                "sample_size": sample_size,
            }
        )
    if not bands:
        raise ValueError("No valid ranking bands were parsed")
    return bands


def ranking_pages_for_band(rank_start: int, rank_end: int) -> list[int]:
    first_page = math.ceil(rank_start / RANKING_PAGE_SIZE)
    last_page = math.ceil(rank_end / RANKING_PAGE_SIZE)
    return list(range(first_page, last_page + 1))


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


def build_sampling_manifest(
    client: OsuApiClient,
    bands: list[dict[str, Any]],
    ranking_type: str,
    random_seed: int,
    raw_dir: Path,
) -> list[dict[str, Any]]:
    sampled_users_path = raw_dir / "sampled_users.jsonl"
    ranking_pages_path = raw_dir / "ranking_pages.jsonl"
    if sampled_users_path.exists():
        return read_jsonl(sampled_users_path)

    sampled_users: list[dict[str, Any]] = []
    for band in bands:
        candidates: list[dict[str, Any]] = []
        pages = ranking_pages_for_band(band["rank_start"], band["rank_end"])
        for page in pages:
            ranking_response = client.get_rankings(ranking_type, page)
            append_jsonl(
                ranking_pages_path,
                {
                    "page": page,
                    "ranking_type": ranking_type,
                    "band_label": band["label"],
                    "collected_at": utc_now_iso(),
                    "response": ranking_response,
                },
            )
            ranking_entries = ranking_response.get("ranking") or []
            for index_on_page, entry in enumerate(ranking_entries):
                approx_rank = (page - 1) * RANKING_PAGE_SIZE + index_on_page + 1
                if approx_rank < band["rank_start"] or approx_rank > band["rank_end"]:
                    continue
                user = entry.get("user") or {}
                user_id = user.get("id")
                if user_id is None:
                    continue
                candidates.append(
                    {
                        "user_id": int(user_id),
                        "band_label": band["label"],
                        "band_index": band["index"],
                        "approx_rank": approx_rank,
                        "ranking_page": page,
                    }
                )
        rng = random.Random(random_seed + band["index"])
        if len(candidates) <= band["sample_size"]:
            band_sample = candidates
        else:
            band_sample = rng.sample(candidates, band["sample_size"])
        sampled_users.extend(sorted(band_sample, key=lambda item: item["approx_rank"]))

    sampled_users = sorted(sampled_users, key=lambda item: (item["band_index"], item["approx_rank"], item["user_id"]))
    for sampled_user in sampled_users:
        append_jsonl(sampled_users_path, sampled_user)
    return sampled_users


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

    for sampled_user in sampled_users:
        user_id = sampled_user["user_id"]
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
        write_json(
            state_path,
            {
                "processed_user_ids": sorted(processed_user_ids),
                "processed_user_count": len(processed_user_ids),
                "total_sampled_user_count": len(sampled_users),
                "last_updated_at": utc_now_iso(),
            },
        )


def collect_missing_beatmaps(client: OsuApiClient, raw_dir: Path, state_path: Path) -> None:
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

    missing_ids = sorted(referenced_beatmap_ids - cached_beatmap_ids)
    if not missing_ids:
        return

    beatmaps = client.get_beatmaps(missing_ids)
    for beatmap in beatmaps:
        beatmap_id = beatmap.get("id")
        if beatmap_id is None:
            continue
        append_jsonl(beatmaps_path, beatmap)
        cached_beatmap_ids.add(int(beatmap_id))

    state["cached_beatmap_ids"] = sorted(cached_beatmap_ids)
    state["last_updated_at"] = utc_now_iso()
    write_json(state_path, state)


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
        "seed_band": sampled_user["band_label"],
        "seed_user_rank": sampled_user["approx_rank"],
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


def build_profile_summary(rows: list[dict[str, Any]], metadata: dict[str, Any], csv_name: str) -> str:
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
    band_counts = Counter(row["seed_band"] for row in rows)
    mod_counts = Counter((row["mods_raw"] or "NM") for row in rows)
    collected_values = sorted({row["collected_at"] for row in rows if row.get("collected_at")})

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
        f"- Band spec: `{metadata['band_spec']}`",
        f"- Recent scores per user: `{metadata['recent_scores_per_user']}`",
        f"- Best scores per user: `{metadata['best_scores_per_user']}`",
        "",
        "## Size",
        "",
        f"- Rows: `{total_rows}`",
        f"- Unique users: `{unique_users}`",
        f"- Unique beatmaps: `{unique_beatmaps}`",
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
        "## Rows Per Ranking Band",
        "",
        *[f"- `{band}`: `{count}`" for band, count in sorted(band_counts.items())],
        "",
        "## Top Mods",
        "",
        *[f"- `{mod}`: `{count}`" for mod, count in mod_counts.most_common(10)],
        "",
        "## Observations",
        "",
        "- This export uses deterministic band sampling, so re-running with the same config should preserve the sampled user pool.",
        "- JSONL storage keeps raw data append-friendly and much easier to inspect than large directories of tiny JSON files.",
        "- `best` score rows improve positive-label coverage, but source mix should be tracked during training.",
        "- Resume safety comes from append-only user snapshots, beatmap cache reuse, and state.json checkpoints.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    load_local_env()

    output_dir = build_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "ruleset": RULESET,
        "band_spec": args.band_spec,
        "ranking_type": args.ranking_type,
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
    client = OsuApiClient(
        client_id=client_id,
        client_secret=client_secret,
        timeout_seconds=args.timeout_seconds,
        request_delay_seconds=args.request_delay_seconds,
    )

    bands = parse_band_spec(args.band_spec)
    state_path = output_dir / "state.json"
    sampled_users = build_sampling_manifest(client, bands, args.ranking_type, args.random_seed, raw_dir)
    collect_user_snapshots(client, sampled_users, raw_dir, args.recent_scores_per_user, args.best_scores_per_user, state_path)
    collect_missing_beatmaps(client, raw_dir, state_path)

    rows = build_rows(raw_dir)
    csv_name = "osu_ranked_attempts_v1.csv"
    csv_path = output_dir / csv_name
    write_csv(csv_path, rows)

    export_finished_at = utc_now_iso()
    export_duration_seconds = round(
        datetime.fromisoformat(export_finished_at.replace("Z", "+00:00")).timestamp()
        - datetime.fromisoformat(export_started_at.replace("Z", "+00:00")).timestamp(),
        3,
    )
    metadata = {
        "export_started_at": export_started_at,
        "export_finished_at": export_finished_at,
        "export_duration_seconds": export_duration_seconds,
        "ranking_type": args.ranking_type,
        "random_seed": args.random_seed,
        "band_spec": args.band_spec,
        "recent_scores_per_user": args.recent_scores_per_user,
        "best_scores_per_user": args.best_scores_per_user,
        "sampled_user_count": len(sampled_users),
        "exported_row_count": len(rows),
    }
    write_json(output_dir / "export_metadata.json", metadata)
    (output_dir / "profiling_summary.md").write_text(build_profile_summary(rows, metadata, csv_name), encoding="utf-8")

    print(f"Wrote {len(rows)} rows to {csv_path.as_posix()}")
    print(f"Run directory: {output_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
