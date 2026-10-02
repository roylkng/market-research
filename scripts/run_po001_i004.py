from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i004 import run_po001_i004


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_verified_json(
    path: Path,
    manifest_path: Path,
    *,
    file_hash_field: str,
    internal_hash_field: str,
    payload_hash_field: str,
    label: str,
) -> tuple[dict, dict]:
    raw = path.read_bytes()
    payload = _load_json(path)
    manifest = _load_json(manifest_path)
    if sha256_bytes(raw) != manifest[file_hash_field]:
        raise ValueError(f"{label} file SHA mismatch")
    if payload[payload_hash_field] != manifest[internal_hash_field]:
        raise ValueError(f"{label} internal SHA mismatch")
    return payload, manifest


def _load_verified_gzip(
    path: Path,
    manifest_path: Path,
    *,
    file_hash_field: str,
    internal_hash_field: str,
    payload_hash_field: str,
    label: str,
) -> tuple[dict, dict]:
    raw = path.read_bytes()
    payload = load_canonical_gzip_json(raw)
    manifest = _load_json(manifest_path)
    if sha256_bytes(raw) != manifest[file_hash_field]:
        raise ValueError(f"{label} gzip SHA mismatch")
    if payload[payload_hash_field] != manifest[internal_hash_field]:
        raise ValueError(f"{label} internal SHA mismatch")
    return payload, manifest


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
        description="Run frozen PO001 I004 RM001-v3 risk treatment study"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--alpha-model", type=Path, required=True)
    parser.add_argument("--alpha-model-manifest", type=Path, required=True)
    parser.add_argument("--control-risk", type=Path, required=True)
    parser.add_argument("--control-risk-manifest", type=Path, required=True)
    parser.add_argument("--treatment-risk", type=Path, required=True)
    parser.add_argument("--treatment-risk-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())

    alpha, alpha_manifest = _load_verified_json(
        args.alpha_model,
        args.alpha_model_manifest,
        file_hash_field="file_sha256",
        internal_hash_field="internal_model_sha256",
        payload_hash_field="model_sha256",
        label="I004 alpha model",
    )
    control_risk, control_manifest = _load_verified_gzip(
        args.control_risk,
        args.control_risk_manifest,
        file_hash_field="gzip_file_sha256",
        internal_hash_field="internal_rm001_state_sha256",
        payload_hash_field="state_sha256",
        label="I004 control risk",
    )
    treatment_risk, treatment_manifest = _load_verified_gzip(
        args.treatment_risk,
        args.treatment_risk_manifest,
        file_hash_field="gzip_file_sha256",
        internal_hash_field="internal_rm001_v3_state_sha256",
        payload_hash_field="state_sha256",
        label="I004 treatment risk",
    )

    report = run_po001_i004(
        delivery_feature_panel=features,
        market_panel=market,
        pinned_alpha_model=alpha,
        control_risk_state=control_risk,
        treatment_risk_state=treatment_risk,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    report_path = args.output / "po001-i004-report.json.gz"
    report_path.write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "decision_session": report["decision_session"],
        "horizon_sessions": report["horizon_sessions"],
        "portfolio_nav_inr": report["portfolio_nav_inr"],
        "realized_outcome_opened": report["realized_outcome_opened"],
        "alpha_manifest": alpha_manifest,
        "control_risk_manifest": control_manifest,
        "treatment_risk_manifest": treatment_manifest,
        "common_identity_count": report["common_identity_count"],
        "execution_contract": report["execution_contract"],
        "control_reproduction_passed": report[
            "control_reproduction_passed"
        ],
        "control_rm001_v1": report["control_rm001_v1"],
        "treatment_rm001_v3": report["treatment_rm001_v3"],
        "treatment_minus_control": report["treatment_minus_control"],
        "weight_changes": report["weight_changes"],
        "common_factor_exposure_changes": report[
            "common_factor_exposure_changes"
        ],
        "new_factor_exposures": report["new_factor_exposures"],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
