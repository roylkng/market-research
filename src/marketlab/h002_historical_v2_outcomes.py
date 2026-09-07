from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from marketlab import h002_historical_outcomes as base_outcomes
from marketlab.h002_historical_outcomes import canonical_hash
from marketlab.h002_historical_outcomes_fast import cluster_bootstrap_spread_fast

PHASE_A_ID = "A_SIGNAL_CAPTURE_ONLY"
PHASE_B_ID = "B_OUTCOME_RECONSTRUCTION"
REPLAY_RULE_ID = "H002-HR002"
SOURCE_SIGNAL_RULE_ID = "H002-R001"


class HistoricalOutcomeV2Error(ValueError):
    """Raised when H002-HR002 outcomes cross their frozen evidence boundary."""


def load_phase_a_manifest_v2(
    path: str | Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalOutcomeV2Error(f"could not load HR002 Phase-A manifest: {exc}") from exc
    if not isinstance(document, dict):
        raise HistoricalOutcomeV2Error("HR002 Phase-A manifest root must be an object")
    declared = document.get("manifest_sha256")
    if declared != expected_sha256:
        raise HistoricalOutcomeV2Error(
            f"HR002 Phase-A identity changed: expected={expected_sha256}, observed={declared}"
        )
    unsigned = dict(document)
    unsigned.pop("manifest_sha256", None)
    actual = canonical_hash(unsigned)
    if actual != declared:
        raise HistoricalOutcomeV2Error(
            f"HR002 Phase-A hash mismatch: declared={declared}, recomputed={actual}"
        )
    if document.get("phase") != PHASE_A_ID:
        raise HistoricalOutcomeV2Error("HR002 outcomes require Phase-A signal capture")
    if document.get("replay_rule_id") != REPLAY_RULE_ID:
        raise HistoricalOutcomeV2Error("unexpected HR002 replay rule")
    if document.get("source_signal_rule_id") != SOURCE_SIGNAL_RULE_ID:
        raise HistoricalOutcomeV2Error("HR002 no longer transports H002-R001")
    if document.get("outcome_data_included") is not False:
        raise HistoricalOutcomeV2Error("HR002 Phase A unexpectedly contains outcome data")
    if int(document.get("observation_count", -1)) != 600:
        raise HistoricalOutcomeV2Error("HR002 Phase A must contain the frozen 600 observations")
    if int(document.get("status_counts", {}).get("ERROR", 0)):
        raise HistoricalOutcomeV2Error("HR002 Phase A contains unresolved ERROR observations")
    return document


def summarize_phase_b_v2(records: list[dict[str, Any]]) -> dict[str, Any]:
    # The vectorized implementation is algebraically identical to the original
    # company-cluster bootstrap and preserves the frozen 10,000 samples/seed.
    original = base_outcomes._cluster_bootstrap_spread
    base_outcomes._cluster_bootstrap_spread = cluster_bootstrap_spread_fast
    try:
        return base_outcomes.summarize_phase_b(records)
    finally:
        base_outcomes._cluster_bootstrap_spread = original


def phase_b_manifest_v2(
    *,
    phase_a_manifest_sha256: str,
    generated_at_utc: str,
    records: list[dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    summary = summarize_phase_b_v2(records)
    document = {
        "schema_version": 1,
        "phase": PHASE_B_ID,
        "replay_rule_id": REPLAY_RULE_ID,
        "source_signal_rule_id": SOURCE_SIGNAL_RULE_ID,
        "phase_a_manifest_sha256": phase_a_manifest_sha256,
        "generated_at_utc": generated_at_utc,
        "outcome_data_included": True,
        "live_capital_allowed": False,
        "cohort_bias_label": "SURVIVORSHIP_SENSITIVE_FIXED_2026_COHORT",
        "records": records,
        "summary": summary,
        "evidence": evidence,
    }
    document["manifest_sha256"] = canonical_hash(document)
    return document
