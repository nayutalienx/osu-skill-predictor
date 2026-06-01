#!/usr/bin/env python3
"""Print or watch progress for a country-seeded dataset collection run."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="Run directory under data/raw/")
    parser.add_argument("--watch", type=float, default=0.0, help="Refresh interval in seconds. Default: print once.")
    parser.add_argument("--clear", action="store_true", help="Clear the terminal between refreshes in watch mode.")
    return parser.parse_args()


def iso_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed_seconds(started_at: str | None, finished_at: str | None = None) -> int | None:
    started = iso_to_datetime(started_at)
    if started is None:
        return None
    ended = iso_to_datetime(finished_at) or datetime.now(timezone.utc)
    return int((ended - started).total_seconds())


def format_band_counts(title: str, counts: dict[str, Any]) -> list[str]:
    lines = [title]
    if not counts:
        lines.append("- none")
        return lines
    for band, count in sorted(counts.items()):
        lines.append(f"- {band}: {count}")
    return lines


def render_progress(run_dir: Path) -> str:
    state = read_json(run_dir / "state.json", {})
    metadata = read_json(run_dir / "export_metadata.json", {})
    config = read_json(run_dir / "config.json", {})

    phase = state.get("phase", "unknown")
    started_at = state.get("export_started_at") or metadata.get("export_started_at")
    finished_at = metadata.get("export_finished_at") if phase == "done" else None
    elapsed = elapsed_seconds(started_at, finished_at)

    processed = state.get("processed_user_count", 0)
    total = state.get("total_sampled_user_count") or state.get("sampled_user_count") or 0
    progress = (processed / total * 100.0) if total else 0.0

    lines = [
        f"Run: {run_dir}",
        f"Phase: {phase}",
        f"Started at: {started_at or ''}",
        f"Last updated at: {state.get('last_updated_at', '')}",
        f"Elapsed seconds: {elapsed if elapsed is not None else ''}",
        f"Ranking type: {state.get('ranking_type') or config.get('ranking_type', '')}",
        f"Country leaderboard size: {state.get('top_country_total_available', '')}",
        f"Selected countries: {state.get('selected_country_count', '')}",
        f"Users processed: {processed} / {total} ({progress:.2f}%)",
        f"Unique sampled users: {state.get('unique_sampled_user_count', '')}",
        f"Ranking pages fetched: {state.get('ranking_pages_fetched', '')}",
        f"Beatmaps cached: {state.get('cached_beatmap_count', '')}",
        f"Beatmaps referenced: {state.get('referenced_beatmap_count', '')}",
        f"CSV rows: {state.get('csv_row_count', '')}",
        f"Current country: {state.get('current_country_code', '')}",
        f"Current page: {state.get('current_page', '')}",
        f"Note: {state.get('note', '')}",
        "",
        *format_band_counts("Sampled users per country:", state.get("sampled_country_counts") or {}),
        "",
        *format_band_counts("Processed users per country:", state.get("processed_country_counts") or {}),
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")

    while True:
        if args.clear:
            print("\033[2J\033[H", end="")
        print(render_progress(run_dir), flush=True)
        if args.watch <= 0:
            break
        state = read_json(run_dir / "state.json", {})
        if state.get("phase") == "done":
            break
        time.sleep(args.watch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
