from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.alpha_options_source_d006 import (
    audit_historical_option_source_d006,
)
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
        description="Run frozen AE001 D006 row-level stock-options source audit"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market_bytes = args.market_panel.read_bytes()
    market = load_canonical_gzip_json(market_bytes)

    report = audit_historical_option_source_d006(
        market_panel=market,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "d006-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "diagnostic_id": report["diagnostic_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "market_panel_sha256": report["market_panel_sha256"],
        "market_artifact_sha256": sha256_bytes(market_bytes),
        "session_count": report["session_count"],
        "ready_session_count": report["ready_session_count"],
        "unavailable_session_count": report["unavailable_session_count"],
        "parser_rejected_session_count": report[
            "parser_rejected_session_count"
        ],
        "total_stock_option_row_count": report[
            "total_stock_option_row_count"
        ],
        "total_accepted_contract_row_count": report[
            "total_accepted_contract_row_count"
        ],
        "row_exclusion_counts": report["row_exclusion_counts"],
        "ambiguous_logical_contract_count": report[
            "ambiguous_logical_contract_count"
        ],
        "surface_exclusion_counts": report["surface_exclusion_counts"],
        "usable_symbol_distribution": report[
            "usable_symbol_distribution"
        ],
        "low_coverage_session_count_lt_75": report[
            "low_coverage_session_count_lt_75"
        ],
        "viability_gates": report["viability_gates"],
        "all_viability_gates_passed": report[
            "all_viability_gates_passed"
        ],
        "source_hashes_sha256": report["source_hashes_sha256"],
        "future_returns_opened": False,
        "model_fit_started": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
