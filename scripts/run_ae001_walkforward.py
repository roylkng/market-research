from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_walkforward import run_ridge_walkforward


def _fold(value: str) -> dict[str, str]:
    parts = value.split(":", maxsplit=1)
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError("fold must be START:END")
    return {"start": parts[0], "end": parts[1]}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AE001 one-session purged ridge walk-forward"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fold", type=_fold, action="append", required=True)
    parser.add_argument("--l2", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    report = run_ridge_walkforward(
        feature_panel=features,
        market_panel=market,
        folds=args.fold,
        l2=args.l2,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "walkforward-report.json.gz").write_bytes(
        canonical_gzip_json(report)
    )
    summary = {
        key: value
        for key, value in report.items()
        if key not in {"oos_predictions"}
    }
    # Keep the human-readable summary compact while preserving full per-session
    # metrics and predictions in the deterministic gzip report.
    summary["ridge"] = {
        key: value
        for key, value in report["ridge"].items()
        if key != "session_metrics"
    }
    summary["momentum_20_baseline"] = {
        key: value
        for key, value in report["momentum_20_baseline"].items()
        if key != "session_metrics"
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
