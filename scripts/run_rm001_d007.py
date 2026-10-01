from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.alpha_acquisition import http_fetcher
from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.rm001_size_source import run_d007_security_master_audit


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
        description="Run frozen RM001 D007 NSE security-master size-source audit"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    result = run_d007_security_master_audit(
        market_panel=market,
        fetcher=http_fetcher(
            attempts=args.attempts,
            timeout=args.timeout_seconds,
        ),
        store_root=args.store,
        captured_at_utc=datetime.now(UTC),
    )
    _write_json(args.output, result)
    print(
        json.dumps(
            {
                "diagnostic_id": result["diagnostic_id"],
                "expected_session_count": result["expected_session_count"],
                "ready_session_count": result["ready_session_count"],
                "minimum_exact_join_coverage": result[
                    "minimum_exact_join_coverage"
                ],
                "minimum_positive_issued_size_coverage": result[
                    "minimum_positive_issued_size_coverage"
                ],
                "minimum_positive_market_cap_coverage": result[
                    "minimum_positive_market_cap_coverage"
                ],
                "minimum_positive_free_float_capital_coverage": result[
                    "minimum_positive_free_float_capital_coverage"
                ],
                "maximum_duplicate_real_eq_identity_count": result[
                    "maximum_duplicate_real_eq_identity_count"
                ],
                "total_market_cap_source_passed": result[
                    "total_market_cap_source_passed"
                ],
                "free_float_market_cap_source_passed": result[
                    "free_float_market_cap_source_passed"
                ],
                "sector_source_passed": result["sector_source_passed"],
                "result_sha256": result["result_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
