from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from marketlab import h002_historical_outcomes as base_outcomes
from marketlab.h002_historical_outcomes import canonical_hash
from marketlab.h002_historical_outcomes_fast import cluster_bootstrap_spread_fast

PHASE_A_ID = "A_SIGNAL_CAPTURE_ONLY"
PHASE_B_ID = "B_OUTCOME_RECONSTRUCTION"
EXPERIMENT_ID = "H002-HR003"
MECHANICS_RULE_ID = "H002-HR002"
SOURCE_SIGNAL_RULE_ID = "H002-R001"
EXPECTED_OBSERVATIONS = 919
EXPECTED_SIGNALS = 568


class HistoricalPitOutcomeError(ValueError):
    """Raised when point-in-time historical outcomes cross the frozen evidence boundary."""


def load_phase_a_manifest_pit(
    path: str | Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalPitOutcomeError(
            f"could not load HR003 point-in-time Phase-A manifest: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise HistoricalPitOutcomeError("HR003 Phase-A manifest root must be an object")
    declared = document.get("manifest_sha256")
    if declared != expected_sha256:
        raise HistoricalPitOutcomeError(
            f"HR003 Phase-A identity changed: expected={expected_sha256}, observed={declared}"
        )
    unsigned = dict(document)
    unsigned.pop("manifest_sha256", None)
    actual = canonical_hash(unsigned)
    if actual != declared:
        raise HistoricalPitOutcomeError(
            f"HR003 Phase-A hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("phase") != PHASE_A_ID:
        raise HistoricalPitOutcomeError("HR003 outcomes require Phase-A signal capture")
    if document.get("experiment_id") != EXPERIMENT_ID:
        raise HistoricalPitOutcomeError("unexpected HR003 experiment identity")
    if document.get("mechanics_rule_id") != MECHANICS_RULE_ID:
        raise HistoricalPitOutcomeError("HR003 no longer transports the frozen HR002 mechanics")
    if document.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalPitOutcomeError("HR003 no longer transports H002-R001")
    if document.get("outcome_data_included") is not False:
        raise HistoricalPitOutcomeError("HR003 Phase A unexpectedly contains outcome data")
    if document.get("live_capital_allowed") is not False:
        raise HistoricalPitOutcomeError("historical point-in-time Phase A cannot authorize capital")
    if document.get("cohort_bias_label") != "POINT_IN_TIME_NIFTY200_MEMBERSHIP_NON_FINANCIAL":
        raise HistoricalPitOutcomeError("HR003 point-in-time cohort label changed")
    if int(document.get("observation_count", -1)) != EXPECTED_OBSERVATIONS:
        raise HistoricalPitOutcomeError(
            f"HR003 Phase A must contain {EXPECTED_OBSERVATIONS} observations"
        )
    if int(document.get("status_counts", {}).get("SIGNAL", -1)) != EXPECTED_SIGNALS:
        raise HistoricalPitOutcomeError(
            f"HR003 Phase A must contain {EXPECTED_SIGNALS} executable signals"
        )
    if int(document.get("status_counts", {}).get("ERROR", 0)):
        raise HistoricalPitOutcomeError("HR003 Phase A contains unresolved ERROR observations")
    return document


def _records_for_cluster_statistics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use identity-preserving alias clusters without changing retained outcome records."""

    statistical = copy.deepcopy(records)
    for record in statistical:
        cluster = str(record.get("statistical_cluster_symbol") or "").strip().upper()
        if cluster:
            record["symbol"] = cluster
    return statistical


def summarize_phase_b_pit(records: list[dict[str, Any]]) -> dict[str, Any]:
    original = base_outcomes._cluster_bootstrap_spread
    base_outcomes._cluster_bootstrap_spread = cluster_bootstrap_spread_fast
    try:
        return base_outcomes.summarize_phase_b(_records_for_cluster_statistics(records))
    finally:
        base_outcomes._cluster_bootstrap_spread = original


def phase_b_manifest_pit(
    *,
    phase_a_manifest_sha256: str,
    generated_at_utc: str,
    records: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    summary = summarize_phase_b_pit(records)
    document = {
        "schema_version": 1,
        "phase": PHASE_B_ID,
        "replay_rule_id": EXPERIMENT_ID,
        "mechanics_rule_id": MECHANICS_RULE_ID,
        "source_signal_rule_id": SOURCE_SIGNAL_RULE_ID,
        "phase_a_manifest_sha256": phase_a_manifest_sha256,
        "generated_at_utc": generated_at_utc,
        "outcome_data_included": True,
        "live_capital_allowed": False,
        "cohort_bias_label": "POINT_IN_TIME_NIFTY200_MEMBERSHIP_NON_FINANCIAL",
        "records": records,
        "summary": summary,
        "evidence": evidence,
    }
    document["manifest_sha256"] = canonical_hash(document)
    return document
