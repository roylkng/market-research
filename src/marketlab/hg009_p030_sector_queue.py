"""HG009 P030: build the original 300-company industry source-acquisition queue.

Post-entry index matches are *discoverability leads*, not pre-entry
classification evidence. No H1/H5 market returns are read or inferred.
This is a source readiness diagnostic, not a trial-registration event.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import (
    load_hg009_inputs,
    verify_hg009_controls,
)

AUDIT_ID = "HG009-P030-20261021-SECTOR-PROVENANCE-READINESS-v1"
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
ENTRY = "2026-10-15"
INDEX_SOURCE = "2026-10-16"
MIN_OVERALL = 0.95
MIN_PER_ARM = 0.90
PATHS = {
    "p026": (
        "research/hg009/hg009-p026-postentry-sector-coverage-v1.json",
        "75bd288b96c30886111d969ab78cea3ecea5fc9f",
        "report_sha256",
    ),
    "p027": (
        "research/hg009/hg009-p027-h1-no-alpha-next-cohort-gate-v1.json",
        "420d95a4b7713848817ed526ca07a19f63ebd7ce",
        "report_sha256",
    ),
}


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _load_pinned(root: Path, key: str) -> tuple[dict[str, Any], dict[str, str]]:
    path, blob, sig = PATHS[key]
    raw = (root / path).read_bytes()
    if _git_blob(raw) != blob:
        raise AlphaContractError(f"P030 original {key} Git source blob changed")
    source = json.loads(raw)
    if not isinstance(source, dict):
        raise AlphaContractError("P030 original source not a JSON object")
    unsigned = copy.deepcopy(source)
    stored_sha = unsigned.pop(sig, None)
    if stored_sha != digest(unsigned):
        raise AlphaContractError(f"P030 tampered original {key} report SHA")
    return source, {
        "path": path,
        "pinned_git_blob_sha": blob,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "signed_packet_sha256": stored_sha,
    }


def build_sector_audit(
    *,
    original: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
    p026: dict[str, Any],
    p027: dict[str, Any],
    source_receipts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    verify_hg009_controls(controls, source=original, selected=selected)
    if (
        p026.get("report_id")
        != "HG009-P026-ORIGINAL-SECTOR-COVERAGE-AND-IDENTIFIABILITY-v1"
        or p026.get("frozen_300_total") != 300
        or p026.get("original_first_entry_session") != ENTRY
        or p026.get("source_original_NSE_report_date") != INDEX_SOURCE
        or p026.get("source_report_session_is_after_original_entry") is not True
        or p026.get("original_source_actual_first_retrieval_timestamp_verified_here")
        is not False
        or p026.get("posthoc_source_reconstruction_must_not_change_h1_h5")
        is not True
        or p027.get("result_state")
        != "NO_SUPPORTED_INVESTABLE_ALPHA_NOT_ALPHA_DISPROVEN"
        or p027.get("industry_date_is_after_first_cohort_entry") is not True
        or p027.get("pre_entry_retroactive_sector_source_admissible") is not False
        or p027.get("minimum_next_trial_industry_coverage_total") != MIN_OVERALL
        or p027.get("minimum_next_trial_industry_coverage_per_arm") != MIN_PER_ARM
        or p027["next_experiment_protocol"].get("next_experiment_active") is not False
    ):
        raise AlphaContractError("P030 original no-alpha/sector-source protocol changed")

    arms = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    expected = {}
    for arm in ARMS:
        members = arms[arm]
        if len(members) != 100:
            raise AlphaContractError("P030 frozen arm has wrong denominator")
        for member in members:
            pair = (member["symbol"], member["isin"])
            if pair in expected:
                raise AlphaContractError("P030 duplicate frozen symbol/ISIN")
            expected[pair] = arm
    if len(expected) != 300:
        raise AlphaContractError("P030 original 300 identities not conserved")

    observed = p026.get("all_source_identity_rows")
    if not isinstance(observed, list) or len(observed) != 300:
        raise AlphaContractError("P030 original index subset lost identities")
    matched = Counter()
    tasks = []
    encountered = set()
    for row in observed:
        key = (row.get("symbol"), row.get("frozen_isin"))
        arm = row.get("arm")
        if key not in expected or expected[key] != arm or key in encountered:
            raise AlphaContractError("P030 original source arm/ISIN changed")
        encountered.add(key)
        found = row.get("original_source_join_exact_symbol_isin") is True
        provisional = row.get("provisional_oct16_index_industry")
        if found and (not isinstance(provisional, str) or not provisional):
            raise AlphaContractError("P030 index match lacks documented industry")
        if not found and provisional is not None:
            raise AlphaContractError("P030 unknown company was sector-imputed")
        if (
            row.get("sector_known_at_original_oct15_entry") is not False
            or row.get("sector_pretrade_model_feature_admitted") is not False
        ):
            raise AlphaContractError("P030 after-entry sector cannot be made pre-entry")
        if found:
            matched[arm] += 1
        tasks.append({
            "arm": arm,
            "original_symbol": key[0],
            "frozen_isin": key[1],
            "oct16_index_subset_sector_candidate": provisional,
            "original_exact_index_join": found,
            "source_status": (
                "POSTENTRY_INDEX_MATCH_FIRST_RETRIEVAL_NOT_VERIFIED"
                if found else "NO_ORIGINAL_OFFICIAL_INDUSTRY_SOURCE"
            ),
            "next_source_to_acquire": (
                "NSE_ORIGINAL_FOUR_TIER_INDUSTRY_AND_ISSUER_AUDITED_SEGMENTS"
            ),
            "original_issuer_raw_source_sha256": None,
            "source_first_retrieved_at_utc": None,
            "verified_before_next_entry": False,
            "sector_and_size_model_eligible": False,
            "financial_reporting_regime_verified": False,
        })
    if len(encountered) != 300:
        raise AlphaContractError("P030 index-matched population was reduced")
    if sum(matched.values()) != p026.get("source_exact_match_count"):
        raise AlphaContractError("P030 original coverage count differs")
    for arm in ARMS:
        original = p026["arm_observations"][arm]
        if matched[arm] != original["exact_source_matches"]:
            raise AlphaContractError(f"P030 original {arm} source coverage changed")

    tasks.sort(key=lambda x: (ARMS.index(x["arm"]), x["original_symbol"]))
    total_provisional = sum(matched.values())
    target_total = int(MIN_OVERALL * 300)
    future_missing_if_provenance_verified = max(0, target_total - total_provisional)
    arm_future_gaps = {
        arm: max(0, int(MIN_PER_ARM * 100) - matched[arm])
        for arm in ARMS
    }
    result: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "as_of_date": "2026-10-21",
        "legacy_first_entry_date": ENTRY,
        "legacy_future_outcomes_not_read": True,
        "legacy_sector_source_date": INDEX_SOURCE,
        "legacy_sector_source_is_post_entry": True,
        "original_signed_source_receipts": source_receipts,
        "per_arm_fixed_original_denominator": 100,
        "original_company_count": 300,
        "original_postentry_index_subset_exact_match_count": total_provisional,
        "postentry_index_subset_matches_by_arm": {
            arm: matched[arm] for arm in ARMS
        },
        "unclassified_in_index_subset_count": 300 - total_provisional,
        "unclassified_in_index_subset_by_arm": {
            arm: 100 - matched[arm] for arm in ARMS
        },
        "source_retrieval_provenance_verified_count": 0,
        "source_independently_verified_before_legacy_entry_count": 0,
        "minimum_next_independent_cohort_overall_coverage": MIN_OVERALL,
        "minimum_next_independent_cohort_each_arm": MIN_PER_ARM,
        "minimum_verified_overall_companies_required": target_total,
        "minimum_verified_companies_per_arm": int(MIN_PER_ARM * 100),
        "additional_index_unclassified_companies_needed_for_95pct_if_postentry_matches_independently_attested": future_missing_if_provenance_verified,
        "additional_by_arm_if_existing_index_matches_provenanced": arm_future_gaps,
        "new_independent_cohort_registered": False,
        "next_cohort_entry_date": None,
        "ready_for_next_prospective_trial": False,
        "readiness_state": "BLOCKED_INSUFFICIENT_PREENTRY_PROVENANCE_AND_SOURCE_COVERAGE",
        "future_source_collection_queue": tasks,
        "using_oct16_sector_for_oct15_regression_forbidden": True,
        "source_filename_annual_report_is_not_independently_verified_sector": True,
        "next_cohort_requires_fresh_frozen_sector_size_liquidity_beta_and_regime": True,
        "next_cohort_requires_multi_date_holdout_and_source_bounded_costs": True,
        "no_current_or_future_stock_expected_return_calculated": True,
        "no_retraining_to_explain_legacy_H1_underperformance": True,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize_sector_audit(root: Path) -> dict[str, Any]:
    original, selected = load_hg009_inputs(root)
    controls = json.loads((
        root / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    p026, rec026 = _load_pinned(root, "p026")
    p027, rec027 = _load_pinned(root, "p027")
    return build_sector_audit(
        original=original,
        selected=selected,
        controls=controls,
        p026=p026,
        p027=p027,
        source_receipts={"p026": rec026, "p027": rec027},
    )


def validate_sector_audit(report: dict[str, Any], root: Path) -> None:
    unsigned = copy.deepcopy(report)
    claimed = unsigned.pop("report_sha256", None)
    if claimed != digest(unsigned):
        raise AlphaContractError("P030 report was modified after source sealing")
    if report != materialize_sector_audit(root):
        raise AlphaContractError("P030 output cannot replay original source receipts")
