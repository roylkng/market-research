from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from marketlab.alpha_history import load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i005 import run_po001_i005


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


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
        description="Run frozen PO001 I005 stable risk-treatment revisit"
    )
    parser.add_argument("--s001-report", type=Path, required=True)
    parser.add_argument("--s001-manifest", type=Path, required=True)
    parser.add_argument("--control-risk", type=Path, required=True)
    parser.add_argument("--treatment-risk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_bytes = args.s001_report.read_bytes()
    report = json.loads(gzip.decompress(report_bytes).decode("utf-8"))
    manifest = _load_json(args.s001_manifest)
    if sha256_bytes(report_bytes) != manifest["gzip_file_sha256"]:
        raise ValueError("I005 pinned S001 gzip hash mismatch")
    if report["report_sha256"] != manifest["internal_report_sha256"]:
        raise ValueError("I005 pinned S001 internal SHA mismatch")

    control_risk = load_canonical_gzip_json(
        args.control_risk.read_bytes()
    )
    treatment_risk = load_canonical_gzip_json(
        args.treatment_risk.read_bytes()
    )

    result = run_po001_i005(
        s001_report=report,
        control_risk_state=control_risk,
        treatment_risk_state=treatment_risk,
    )
    _write_json(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
