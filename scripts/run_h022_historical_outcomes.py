from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.h022_outcomes import build_outcome_panel, summarize_challenge


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen H022-O001 historical challenge outcomes"
    )
    parser.add_argument("--feature-panel", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--index-sessions", required=True)
    parser.add_argument("--stock-prices", required=True)
    parser.add_argument("--corporate-actions", required=True)
    parser.add_argument("--outcome-out", required=True)
    parser.add_argument("--result-out", required=True)
    args = parser.parse_args()

    feature_panel = _load(args.feature_panel)
    universe = _load(args.universe)
    index_sessions = _load(args.index_sessions)
    stock_prices = _load(args.stock_prices)
    corporate_actions = _load(args.corporate_actions)

    if not isinstance(feature_panel, dict):
        raise TypeError("feature panel must be a JSON object")
    if not isinstance(universe, dict):
        raise TypeError("universe must be a JSON object")
    if not isinstance(index_sessions, list):
        raise TypeError("index sessions must be a JSON list")
    if not isinstance(stock_prices, dict):
        raise TypeError("stock prices must be a JSON object")
    if not isinstance(corporate_actions, list):
        raise TypeError("corporate actions must be a JSON list")

    panel = build_outcome_panel(
        feature_panel,
        universe,
        index_sessions,
        stock_prices,
        corporate_actions,
    )
    result = summarize_challenge(panel)
    _write(Path(args.outcome_out), panel)
    _write(Path(args.result_out), result)

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
