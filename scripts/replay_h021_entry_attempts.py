"""Preserve each first H021 NSE source attempt's actual partial/full OHLC.

Reproduces byte-identical prior packet SHA from original Git-held source
reports. Does not require Nifty 500 official index to be published before
recovering issuer-matched equity observations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h021_entry_attempt_replay import materialize_original_entry_attempts
from marketlab.h021_first_entry_intent import (
    build_first_entry_intent,
    git_blob_sha,
    load_pinned_inputs,
)

FIRST_OBSERVATIONS = Path("research/prospective/h021/entry-observations")
INTENT_PATH = Path("research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json")
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
INTENT_GIT_BLOB = "e25f77e1c845456473e624899d4748e306b1225b"
UNIVERSE_GIT_BLOB = "8026e81faee3e913d2fba1dba72d60603b69fa07"


def load_original_frozen_inputs(repo_root: Path) -> tuple[dict, dict]:
    comparison, calendar = load_pinned_inputs()
    raw_intent = (repo_root / INTENT_PATH).read_bytes()
    raw_universe = (repo_root / UNIVERSE_PATH).read_bytes()
    if git_blob_sha(raw_intent) != INTENT_GIT_BLOB:
        raise ValueError("first H021 original source intent changed")
    if git_blob_sha(raw_universe) != UNIVERSE_GIT_BLOB:
        raise ValueError("first H021 original U001 universe changed")
    intent = json.loads(raw_intent)
    universe = json.loads(raw_universe)
    if not isinstance(intent, dict) or not isinstance(universe, dict):
        raise TypeError("first H021 intent/universe must be JSON mappings")
    if intent != build_first_entry_intent(comparison, calendar):
        raise ValueError("stored first H021 selection differs from pre-entry source decision")
    return intent, universe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, default=FIRST_OBSERVATIONS)
    parser.add_argument(
        "--out-root",
        type=Path,
        default=FIRST_OBSERVATIONS / "reconstructed-attempts",
    )
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()

    intent, universe = load_original_frozen_inputs(args.repo_root)
    summary = materialize_original_entry_attempts(
        frozen_intent=intent,
        frozen_universe=universe,
        source_root=args.source_root,
        out_root=args.out_root,
        verify_existing=args.verify_existing,
    )
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
