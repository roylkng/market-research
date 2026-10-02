from __future__ import annotations

import argparse
import gzip
import itertools
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.po001_v4 import KKT_TOLERANCE


SCALAR_LIMITS = {
    "expected_5d_excess_return": 1e-10,
    "annualized_volatility": 1e-9,
    "total_variance_daily": 1e-12,
    "risk_penalty": 1e-11,
    "total_transaction_cost_fraction": 1e-10,
    "objective_utility": 1e-10,
}
MAX_WEIGHT_ABS_DIFF = 1e-10
MAX_WEIGHT_L1_DIFF = 1e-8
EXPECTED_REPLICA_COUNT = 3


def _load(path: Path) -> dict[str, Any]:
    return json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))


def _weights(artifact: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (str(row["symbol"]), str(row["isin"])): float(row["target_weight"])
        for row in artifact["rows"]
    }


def _portfolio_stats(
    reports: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, Any]:
    artifacts = [report[key]["artifact"] for report in reports]
    identity_maps = [_weights(artifact) for artifact in artifacts]
    keys = identity_maps[0].keys()
    if any(mapping.keys() != keys for mapping in identity_maps[1:]):
        raise AlphaContractError(
            f"S001 {key} identity sets differ across replicas"
        )

    max_abs = 0.0
    max_l1 = 0.0
    for left, right in itertools.combinations(identity_maps, 2):
        diffs = [abs(left[identity] - right[identity]) for identity in keys]
        max_abs = max(max_abs, max(diffs, default=0.0))
        max_l1 = max(max_l1, sum(diffs))

    scalar_ranges = {}
    for field in SCALAR_LIMITS:
        if field == "annualized_volatility":
            values = [
                (float(a["total_variance_daily"]) * 252.0) ** 0.5
                for a in artifacts
            ]
        else:
            source_field = (
                "expected_excess_return"
                if field == "expected_5d_excess_return"
                else field
            )
            values = [float(a[source_field]) for a in artifacts]
        scalar_ranges[field] = max(values) - min(values)

    kkt_values = [
        float(a["solver"]["kkt"]["maximum_coordinate_kkt_violation"])
        for a in artifacts
    ]
    scalar_pass = all(
        scalar_ranges[field] <= limit
        for field, limit in SCALAR_LIMITS.items()
    )
    weight_pass = (
        max_abs <= MAX_WEIGHT_ABS_DIFF
        and max_l1 <= MAX_WEIGHT_L1_DIFF
    )
    kkt_pass = max(kkt_values) <= KKT_TOLERANCE

    return {
        "artifact_sha256_values": [
            artifact["artifact_sha256"] for artifact in artifacts
        ],
        "all_artifact_hashes_identical": (
            len({artifact["artifact_sha256"] for artifact in artifacts}) == 1
        ),
        "scalar_ranges": scalar_ranges,
        "scalar_limits": SCALAR_LIMITS,
        "economic_scalar_stability_passed": scalar_pass,
        "max_pairwise_absolute_weight_diff": max_abs,
        "max_pairwise_l1_weight_diff": max_l1,
        "weight_stability_passed": weight_pass,
        "maximum_kkt_violation": max(kkt_values),
        "kkt_tolerance": KKT_TOLERANCE,
        "kkt_passed": kkt_pass,
        "passed": scalar_pass and weight_pass and kkt_pass,
    }


def evaluate(paths: list[Path]) -> dict[str, Any]:
    if len(paths) != EXPECTED_REPLICA_COUNT:
        raise AlphaContractError(
            f"S001 requires exactly {EXPECTED_REPLICA_COUNT} replicas"
        )
    reports = [_load(path) for path in sorted(paths)]
    if any(report.get("study_id") != "PO001-S001-v1" for report in reports):
        raise AlphaContractError("unexpected S001 replica study id")
    if any(report.get("realized_outcome_opened") is not False for report in reports):
        raise AlphaContractError("S001 replica unexpectedly opened outcome")

    invariant_fields = (
        "alpha_model_sha256",
        "control_risk_state_sha256",
        "treatment_risk_state_sha256",
        "common_identity_count",
        "execution_contract",
    )
    for field in invariant_fields:
        first = reports[0][field]
        if any(report[field] != first for report in reports[1:]):
            raise AlphaContractError(
                f"S001 replica invariant differs: {field}"
            )

    control = _portfolio_stats(reports, key="control_rm001_v1")
    treatment = _portfolio_stats(reports, key="treatment_rm001_v3")
    passed = control["passed"] and treatment["passed"]

    result: dict[str, Any] = {
        "schema_version": 1,
        "study_id": "PO001-S001-v1",
        "status": (
            "NUMERICAL_STABILITY_ESTABLISHED"
            if passed
            else "PO001_V4_NUMERICAL_STABILITY_NOT_ESTABLISHED"
        ),
        "replica_count": len(reports),
        "source_report_sha256_values": [
            report["report_sha256"] for report in reports
        ],
        "control_rm001_v1": control,
        "treatment_rm001_v3": treatment,
        "promotion": {
            "po001_v4_numerical_stability_established": passed,
            "rm001_v3_portfolio_revisit_allowed": passed,
            "live_capital_allowed": False,
        },
        "realized_outcome_opened": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen three-replica PO001 S001 stability study"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.root.rglob("replica-report.json.gz"))
    result = evaluate(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    if not result["promotion"]["po001_v4_numerical_stability_established"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
