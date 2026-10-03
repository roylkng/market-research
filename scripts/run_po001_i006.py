from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i006 import run_po001_i006


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
        description="Run frozen PO001 I006 RG001 active-risk scaling study"
    )
    parser.add_argument("--p003-report", type=Path, required=True)
    parser.add_argument("--rg001-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    p003 = load_canonical_gzip_json(args.p003_report.read_bytes())
    rg001 = load_canonical_gzip_json(args.rg001_panel.read_bytes())

    report = run_po001_i006(
        p003_report=p003,
        rg001_panel=rg001,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "po001-i006-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "status": report["status"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "evidence_class": report["evidence_class"],
        "horizon_sessions": report["horizon_sessions"],
        "source": report["source"],
        "eligible_session_count": report["eligible_session_count"],
        "frozen_overlay": report["frozen_overlay"],
        "primary_endpoint": report["primary_endpoint"],
        "secondary": report["secondary"],
        "control": report["control"],
        "treatment": report["treatment"],
        "exposure": report["exposure"],
        "cost_model_status": report["cost_model_status"],
        "interpretation": report["interpretation"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
