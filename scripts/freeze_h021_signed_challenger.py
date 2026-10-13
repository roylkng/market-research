"""Freeze a separate, signed-EPS H021S001 challenger before the NEXT NSE open.

Accept only original H021 v1 prospective source files, and never generate
a 9-Oct-2026 retrospective trading intent. No network or future returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from marketlab.h021 import compare_snapshots, select_primary_top_decile
from marketlab.h021_first_entry_intent import git_blob_sha
from marketlab.h021_legacy_adapter import load_h021_capture_compatible
from marketlab.h021_signed_challenger import (
    build_signed_challenger_intent,
    validate_challenger_intent,
)

UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
UNIVERSE_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"
BATCH_PATH = Path("research/prospective/h021/capture-batches-v1.json")
BATCH_BLOB = "bd18a18af7b055daf4ea4e99ba6eaae7b9960e86"
CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)
CALENDAR_BLOB = "9ac614820a67b0f7b20d8170d15b84df3c996b62"
CAPTURES_DIR = Path("research/prospective/h021/captures")


def _read_pinned_json(root: Path, path: Path, blob: str) -> dict:
    raw = (root / path).read_bytes()
    if git_blob_sha(raw) != blob:
        raise ValueError(f"original H021 Git-blob source changed: {path}")
    source = json.loads(raw)
    if not isinstance(source, dict):
        raise TypeError(f"original H021 source must be mapping: {path}")
    return source


def _capture_path(value: object, date: str) -> Path:
    if not isinstance(value, str):
        raise TypeError("sealed H021 comparison requires explicit capture path")
    expected = CAPTURES_DIR / f"{date}-full-u001-v1.json.gz"
    if Path(value) != expected:
        raise ValueError("comparison source path is not frozen expected capture")
    return expected


def _manifest(path: Path) -> Path:
    return path.with_name(path.name[:-len(".json.gz")] + ".manifest.json")


def prepare_signed_challenger(root: Path, comparison_path: Path, now_utc: str) -> dict:
    universe = _read_pinned_json(root, UNIVERSE_PATH, UNIVERSE_BLOB)
    batches = _read_pinned_json(root, BATCH_PATH, BATCH_BLOB)
    calendar = _read_pinned_json(root, CALENDAR_PATH, CALENDAR_BLOB)
    raw_comp = (root / comparison_path).read_bytes()
    comparison = json.loads(raw_comp)
    if not isinstance(comparison, dict):
        raise TypeError("original comparison must be JSON object")
    date = comparison.get("current_capture_date_ist")
    prior_date = comparison.get("prior_capture_date_ist")
    if not isinstance(date, str) or not isinstance(prior_date, str):
        raise TypeError("original comparison capture dates missing")
    expected_comp = Path("research/prospective/h021/comparisons") / (
        f"{date}-primary-revision-v1.json"
    )
    if comparison_path != expected_comp:
        raise ValueError("H021S001 must use original same-date primary comparison")
    prior_path = _capture_path(comparison.get("prior_capture_path"), prior_date)
    current_path = _capture_path(comparison.get("current_capture_path"), date)

    prior, prior_manifest = load_h021_capture_compatible(
        root / prior_path, universe=universe, batch_spec=batches
    )
    current, current_manifest = load_h021_capture_compatible(
        root / current_path, universe=universe, batch_spec=batches
    )
    reference = [asdict(row) for row in compare_snapshots(prior, current)]
    if reference != comparison.get("revision_observations"):
        raise ValueError("H021S001 primary comparison differs from original validated EPS source")
    original_selected = [row.symbol for row in select_primary_top_decile(
        compare_snapshots(prior, current)
    )]
    if original_selected != comparison.get("primary_top_decile_symbols"):
        raise ValueError("original H021 top-decile selection changed")

    paths = {
        "comparison": comparison_path,
        "prior_gzip": prior_path,
        "prior_manifest": _manifest(prior_path),
        "current_gzip": current_path,
        "current_manifest": _manifest(current_path),
    }
    source_sha = {
        key: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for key, path in paths.items()
    }
    if current_manifest.get("payload_gzip_sha256") != source_sha["current_gzip"]:
        raise ValueError("original current H021 sealed gzip hash mismatch")
    if prior_manifest.get("payload_gzip_sha256") != source_sha["prior_gzip"]:
        raise ValueError("original prior H021 sealed gzip hash mismatch")
    return build_signed_challenger_intent(
        comparison=comparison, prior=prior, current=current,
        manifest=current_manifest, universe=universe, calendar=calendar,
        prepared_at_utc=now_utc, original_source_hashes=source_sha,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    date = args.comparison.name.removesuffix("-primary-revision-v1.json")
    wanted_out = Path("research/prospective/h021/signed-intents") / (
        f"{date}-signed-eps-challenger-v1.json"
    )
    if args.out != wanted_out:
        raise ValueError("prospective H021S001 output path/date mismatch")
    if args.out.exists():
        raise FileExistsError("signed EPS challenger already frozen; never overwrite")
    report = prepare_signed_challenger(
        args.repo_root, args.comparison,
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    validate_challenger_intent(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({
        "id": report["intent_id"],
        "entry_session": report["planned_entry_session_ist"],
        "source_valid_count": report["eligible_h021_comparator_count"],
        "challenger_selected_count": report["challenger_selected_count"],
        "stock_symbols": [x["symbol"] for x in report["challenger_selected"]],
        "original_h021_selection_unchanged": True,
        "future_return_prices_observed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
