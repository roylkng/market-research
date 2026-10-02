from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_regime import build_rg001_panel
from marketlab.events import sha256_bytes


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build AE001 RG001 session-level market regime context"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)
    regime = build_rg001_panel(market)

    args.output.mkdir(parents=True, exist_ok=True)
    regime_bytes = canonical_gzip_json(regime)
    (args.output / "regime-panel.json.gz").write_bytes(regime_bytes)
    summary = {
        "schema_version": 1,
        "panel_id": regime["panel_id"],
        "panel_sha256": regime["panel_sha256"],
        "artifact_sha256": sha256_bytes(regime_bytes),
        "market_panel_sha256": regime["market_panel_sha256"],
        "state_count": regime["state_count"],
        "first_session": regime["rows"][0]["session_date"],
        "last_session": regime["rows"][-1]["session_date"],
        "variable_names": regime["variable_names"],
        "stock_level_alpha": False,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
