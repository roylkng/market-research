from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ab001_p004 import run_ab001_p004
from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
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


def _compact(report: dict) -> dict:
    return {
        key: value
        for key, value in report.items()
        if key != "session_metrics"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AB001 P004 regime-conditioned alpha selector"
    )
    parser.add_argument("--p003-report", type=Path, required=True)
    parser.add_argument("--regime-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    p003 = load_canonical_gzip_json(args.p003_report.read_bytes())
    regime = load_canonical_gzip_json(args.regime_panel.read_bytes())

    report = run_ab001_p004(
        p003_report=p003,
        regime_panel=regime,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "ab001-p004-report.json.gz").write_bytes(report_bytes)

    primary = report["selector_minus_always_futures_inference"]["metrics"]
    equal = report["selector_minus_static_equal_inference"]["metrics"]
    summary = {
        "schema_version": 1,
        "pilot_id": report["pilot_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "horizon_sessions": report["horizon_sessions"],
        "source": report["source"],
        "training_contract": report["training_contract"],
        "eligible_selector_session_count": report[
            "eligible_selector_session_count"
        ],
        "selector": _compact(report["selector"]),
        "always_futures_delta": _compact(report["always_futures_delta"]),
        "static_equal_blend": _compact(report["static_equal_blend"]),
        "selector_minus_always_futures_inference": {
            "rank_ic": primary["rank_ic"],
            "top_decile_excess": primary["top_decile_excess"],
            "top_minus_bottom_spread": primary[
                "top_minus_bottom_spread"
            ],
        },
        "selector_minus_static_equal_inference": {
            "rank_ic": equal["rank_ic"],
            "top_decile_excess": equal["top_decile_excess"],
            "top_minus_bottom_spread": equal[
                "top_minus_bottom_spread"
            ],
        },
        "selector_choice_counts": report["selector_choice_counts"],
        "selector_directional_accuracy": report[
            "selector_directional_accuracy"
        ],
        "primary_endpoint": report["primary_endpoint"],
        "secondary_may_rescue_primary": False,
        "prospective_claim_allowed": False,
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
