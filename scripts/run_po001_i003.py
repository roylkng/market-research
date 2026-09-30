from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.alpha_history import canonical_gzip_json, load_canonical_gzip_json
from marketlab.events import sha256_bytes
from marketlab.po001_i003 import run_po001_i003


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


def _compact_surface(surface: dict) -> dict:
    return {
        key: value
        for key, value in surface.items()
        if key != "top_holdings"
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen PO001 I003 stock-specific impact snapshot"
    )
    parser.add_argument("--market-panel", type=Path, required=True)
    parser.add_argument("--feature-panel", type=Path, required=True)
    parser.add_argument("--action-ledger", type=Path, required=True)
    parser.add_argument("--risk-state", type=Path, required=True)
    parser.add_argument("--risk-state-manifest", type=Path, required=True)
    parser.add_argument("--canonical-risk-state", type=Path, required=True)
    parser.add_argument("--alpha-model", type=Path, required=True)
    parser.add_argument("--alpha-model-manifest", type=Path, required=True)
    parser.add_argument("--control-artifact", type=Path, required=True)
    parser.add_argument("--control-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    market = load_canonical_gzip_json(args.market_panel.read_bytes())
    features = load_canonical_gzip_json(args.feature_panel.read_bytes())
    actions = load_canonical_gzip_json(args.action_ledger.read_bytes())
    risk_bytes = args.risk_state.read_bytes()
    risk = load_canonical_gzip_json(risk_bytes)
    risk_manifest = json.loads(
        args.risk_state_manifest.read_text(encoding="utf-8")
    )
    if not isinstance(risk_manifest, dict):
        raise TypeError("I003 pinned risk manifest must be a JSON object")
    if sha256_bytes(risk_bytes) != risk_manifest["gzip_file_sha256"]:
        raise ValueError("I003 pinned risk gzip hash mismatch")
    if risk["state_sha256"] != risk_manifest[
        "internal_rm001_state_sha256"
    ]:
        raise ValueError("I003 pinned risk internal SHA mismatch")
    canonical_risk = load_canonical_gzip_json(
        args.canonical_risk_state.read_bytes()
    )
    alpha_model_bytes = args.alpha_model.read_bytes()
    alpha_model = json.loads(alpha_model_bytes.decode("utf-8"))
    alpha_manifest = json.loads(
        args.alpha_model_manifest.read_text(encoding="utf-8")
    )
    if not isinstance(alpha_model, dict) or not isinstance(alpha_manifest, dict):
        raise TypeError("I003 pinned alpha inputs must be JSON objects")
    if sha256_bytes(alpha_model_bytes) != alpha_manifest["file_sha256"]:
        raise ValueError("I003 pinned alpha file hash mismatch")
    if alpha_model["model_sha256"] != alpha_manifest[
        "internal_model_sha256"
    ]:
        raise ValueError("I003 pinned alpha internal SHA mismatch")

    control_bytes = args.control_artifact.read_bytes()
    control = load_canonical_gzip_json(control_bytes)
    control_manifest = json.loads(
        args.control_manifest.read_text(encoding="utf-8")
    )
    if not isinstance(control_manifest, dict):
        raise TypeError("I003 pinned control manifest must be a JSON object")
    if sha256_bytes(control_bytes) != control_manifest["gzip_file_sha256"]:
        raise ValueError("I003 pinned control gzip hash mismatch")
    if control["artifact_sha256"] != control_manifest[
        "internal_i002_artifact_sha256"
    ]:
        raise ValueError("I003 pinned control internal SHA mismatch")
    if control_manifest["control_optimizer_artifact_sha256"] != (
        "ad77db26c76e54921254aea9e49c30da8b1f044076b57961671229e93100154e"
    ):
        raise ValueError("I003 pinned control optimizer provenance mismatch")

    report = run_po001_i003(
        delivery_feature_panel=features,
        market_panel=market,
        action_ledger=actions,
        risk_state=risk,
        canonical_risk_state=canonical_risk,
        pinned_alpha_model=alpha_model,
        pinned_i002_control=control,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    report_bytes = canonical_gzip_json(report)
    (args.output / "po001-i003-report.json.gz").write_bytes(report_bytes)

    summary = {
        "schema_version": 1,
        "study_id": report["study_id"],
        "report_sha256": report["report_sha256"],
        "report_artifact_sha256": sha256_bytes(report_bytes),
        "decision_session": report["decision_session"],
        "horizon_sessions": report["horizon_sessions"],
        "realized_outcome_opened": report["realized_outcome_opened"],
        "reproduction_gates": report["reproduction_gates"],
        "pinned_risk_manifest": risk_manifest,
        "pinned_alpha_manifest": alpha_manifest,
        "pinned_control_manifest": control_manifest,
        "common_identity_count": report["common_identity_count"],
        "training_example_count": report["training_example_count"],
        "training_last_exit_session": report["training_last_exit_session"],
        "execution_input_distribution": report[
            "execution_input_distribution"
        ],
        "observable_cost_bps": report["observable_cost_bps"],
        "v1_observable_cost_baseline": report[
            "v1_observable_cost_baseline"
        ],
        "v2_nav_surfaces": {
            key: _compact_surface(value)
            for key, value in report["v2_nav_surfaces"].items()
        },
        "primary_nav_inr": report["primary_nav_inr"],
        "primary_delta_vs_v1": report["primary_delta_vs_v1"],
        "impact_contract": report["impact_contract"],
        "interpretation_limits": report["interpretation_limits"],
        "live_capital_allowed": False,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
