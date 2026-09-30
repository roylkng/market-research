from __future__ import annotations

import copy
from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_fundamental import FEATURE_NAMES

D004_ID = "AE001-T008-D004-v1"
EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
D002_PANEL_SHA = (
    "6426dbe7fc47faa8ce440e599d3566ce98fe8d675efc5abb61145c940d6bfd64"
)
D003_PANEL_SHA = (
    "69fdda1d51b7a070849556a53794f224d054270974958ae45eab6555fbaa1e35"
)
PERIOD_SOURCE = {
    "2025-09-30": {
        "diagnostic_id": "AE001-T008-D003-v1",
        "panel_sha256": D003_PANEL_SHA,
        "run_id": 36746275777,
        "artifact_id": 11113075870,
    },
    "2025-12-31": {
        "diagnostic_id": "AE001-T008-D003-v1",
        "panel_sha256": D003_PANEL_SHA,
        "run_id": 36746275777,
        "artifact_id": 11113075870,
    },
    "2026-03-31": {
        "diagnostic_id": "AE001-T008-D002-v1",
        "panel_sha256": D002_PANEL_SHA,
        "run_id": 36742740631,
        "artifact_id": 11111600748,
    },
    "2026-06-30": {
        "diagnostic_id": "AE001-T008-D002-v1",
        "panel_sha256": D002_PANEL_SHA,
        "run_id": 36742740631,
        "artifact_id": 11111600748,
    },
}
MIN_COMPLETE_PER_PERIOD = 60
MIN_TOTAL_COMPLETE = 280


def _validate_source_panel(
    panel: dict[str, Any],
    *,
    diagnostic_id: str,
    expected_sha256: str,
) -> None:
    stored = str(panel.get("panel_sha256") or "")
    unsigned = copy.deepcopy(panel)
    unsigned.pop("panel_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError(
            f"T008 D004 {diagnostic_id} source panel hash mismatch"
        )
    if stored != expected_sha256:
        raise AlphaContractError(
            f"T008 D004 {diagnostic_id} source panel differs from frozen SHA"
        )
    if panel.get("diagnostic_id") != diagnostic_id:
        raise AlphaContractError(
            f"T008 D004 unexpected source diagnostic: {panel.get('diagnostic_id')}"
        )
    if panel.get("universe_sha256") != EXPECTED_UNIVERSE_SHA:
        raise AlphaContractError("T008 D004 source universe SHA mismatch")
    if panel.get("return_outcomes_opened") is not False:
        raise AlphaContractError("T008 D004 source panel contains return outcomes")
    if panel.get("model_fitted") is not False:
        raise AlphaContractError("T008 D004 source panel contains model fit")
    if not isinstance(panel.get("records"), list):
        raise AlphaContractError("T008 D004 source panel records are missing")


def combine_t008_source_panels(
    *,
    d002_panel: dict[str, Any],
    d003_panel: dict[str, Any],
) -> dict[str, Any]:
    _validate_source_panel(
        d002_panel,
        diagnostic_id="AE001-T008-D002-v1",
        expected_sha256=D002_PANEL_SHA,
    )
    _validate_source_panel(
        d003_panel,
        diagnostic_id="AE001-T008-D003-v1",
        expected_sha256=D003_PANEL_SHA,
    )
    sources = {
        "AE001-T008-D002-v1": d002_panel,
        "AE001-T008-D003-v1": d003_panel,
    }

    combined_records = []
    for target_period in sorted(PERIOD_SOURCE):
        source_spec = PERIOD_SOURCE[target_period]
        source_panel = sources[source_spec["diagnostic_id"]]
        candidates = [
            record
            for record in source_panel["records"]
            if str(record.get("target_period_end")) == target_period
        ]
        for source_record in candidates:
            if source_record.get("all_six_features_complete") is not True:
                continue
            features = source_record.get("features")
            if not isinstance(features, dict):
                raise AlphaContractError(
                    "T008 D004 source record feature object is missing"
                )
            if set(features) != set(FEATURE_NAMES):
                raise AlphaContractError(
                    "T008 D004 source record feature set differs from frozen six"
                )
            if any(features[name] is None for name in FEATURE_NAMES):
                raise AlphaContractError(
                    "T008 D004 source record marked complete with missing feature"
                )

            row = copy.deepcopy(source_record)
            source_record_sha = str(row.get("record_sha256") or "")
            if not source_record_sha:
                raise AlphaContractError(
                    "T008 D004 source record hash is missing"
                )
            source_unsigned = dict(row)
            source_unsigned.pop("record_sha256", None)
            if digest(source_unsigned) != source_record_sha:
                raise AlphaContractError(
                    "T008 D004 source record hash mismatch"
                )
            row.pop("record_sha256", None)
            row["source_diagnostic_id"] = source_spec["diagnostic_id"]
            row["source_panel_sha256"] = source_spec["panel_sha256"]
            row["source_workflow_run_id"] = source_spec["run_id"]
            row["source_workflow_artifact_id"] = source_spec["artifact_id"]
            row["source_record_sha256"] = source_record_sha
            row["diagnostic_id"] = D004_ID
            row["record_sha256"] = digest(row)
            combined_records.append(row)

    keys = [
        (str(row["target_period_end"]), str(row["symbol"]))
        for row in combined_records
    ]
    if len(keys) != len(set(keys)):
        raise AlphaContractError(
            "T008 D004 duplicate target-period/symbol record"
        )

    per_period_counts = Counter(
        str(row["target_period_end"]) for row in combined_records
    )
    basis_by_period: dict[str, Counter] = defaultdict(Counter)
    parser_by_period: dict[str, Counter] = defaultdict(Counter)
    for row in combined_records:
        period = str(row["target_period_end"])
        basis_by_period[period][str(row["accounting_basis"])] += 1
        parser_by_period[period][
            (
                f"{row['target_parser_version']}|"
                f"{row['baseline_parser_version']}"
            )
        ] += 1

    per_period = {}
    for target_period in sorted(PERIOD_SOURCE):
        count = int(per_period_counts[target_period])
        per_period[target_period] = {
            "record_count": count,
            "complete_six_feature_count": count,
            "source_diagnostic_id": PERIOD_SOURCE[target_period][
                "diagnostic_id"
            ],
            "source_panel_sha256": PERIOD_SOURCE[target_period][
                "panel_sha256"
            ],
            "basis_counts": dict(sorted(basis_by_period[target_period].items())),
            "parser_pair_counts": dict(
                sorted(parser_by_period[target_period].items())
            ),
            "passes_minimum_complete_rows": count >= MIN_COMPLETE_PER_PERIOD,
        }

    total_complete = len(combined_records)
    feasibility_pass = (
        total_complete >= MIN_TOTAL_COMPLETE
        and all(
            details["passes_minimum_complete_rows"]
            for details in per_period.values()
        )
    )
    panel: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D004_ID,
        "evidence_class": "HISTORICAL_SOURCE_FEASIBILITY_NO_RETURNS",
        "universe_sha256": EXPECTED_UNIVERSE_SHA,
        "source_panels": {
            "d002": {
                "diagnostic_id": "AE001-T008-D002-v1",
                "panel_sha256": D002_PANEL_SHA,
                "run_id": 36742740631,
                "artifact_id": 11111600748,
            },
            "d003": {
                "diagnostic_id": "AE001-T008-D003-v1",
                "panel_sha256": D003_PANEL_SHA,
                "run_id": 36746275777,
                "artifact_id": 11113075870,
            },
        },
        "feature_names": list(FEATURE_NAMES),
        "record_count": total_complete,
        "complete_six_feature_count": total_complete,
        "per_period": per_period,
        "feasibility_thresholds": {
            "minimum_complete_rows_per_target_period": MIN_COMPLETE_PER_PERIOD,
            "minimum_total_complete_rows": MIN_TOTAL_COMPLETE,
        },
        "feasibility_pass": feasibility_pass,
        "records": sorted(
            combined_records,
            key=lambda row: (
                row["target_period_end"],
                row["symbol"],
            ),
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
