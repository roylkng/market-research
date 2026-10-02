from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import SOURCE_URL as CONSTITUENT_SOURCE_URL
from marketlab.rm001_d015 import parse_constituent_csv
from marketlab.rm001_d015_r1 import parse_security_master_all_series

LEDGER_ID = "RM001-SC002-INDUSTRY-SOURCE-LEDGER-v1"
START_OBSERVATION_DATE = date(2026, 10, 2)
MIN_PARENT_ROWS = 700
MIN_PROJECTED_EQ_ROWS = 700
MIN_READY_OBSERVATION_DATES = 5
MIN_READY_TARGET_SESSIONS = 3
ALLOWED_DELETION_FLAGS = {"", "N"}


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_industry_source_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_industry_source_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != LEDGER_ID:
        raise AlphaContractError("unexpected RM001-SC002 ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("RM001-SC002 cannot allow live capital")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("RM001-SC002 attempts must be a list")
    if ledger.get("attempt_count") != len(attempts):
        raise AlphaContractError("RM001-SC002 attempt count mismatch")
    seen_hashes: set[str] = set()
    for index, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict) or attempt.get("seq") != index:
            raise AlphaContractError("RM001-SC002 attempt sequence mismatch")
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = copy.deepcopy(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("RM001-SC002 attempt hash mismatch")
        if stored in seen_hashes:
            raise AlphaContractError("duplicate RM001-SC002 attempt hash")
        seen_hashes.add(stored)
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("RM001-SC002 ledger hash mismatch")


def latest_eligible_sc001_target(
    sc001_ledger: dict[str, Any],
    *,
    observation_date: str,
) -> dict[str, Any]:
    cutoff = date.fromisoformat(observation_date)
    candidates = [
        attempt
        for attempt in sc001_ledger.get("attempts", [])
        if attempt.get("eligible_before_cutoff") is True
        and date.fromisoformat(str(attempt["session_date"])) <= cutoff
    ]
    if not candidates:
        raise AlphaContractError(
            "RM001-SC002 found no eligible AE001-SC001 target session"
        )
    candidates.sort(
        key=lambda row: (
            str(row["session_date"]),
            str(row.get("captured_at_utc") or ""),
            int(row.get("seq") or 0),
        )
    )
    return candidates[-1]


def _identity_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identity_counts = Counter((row["symbol"], row["isin"]) for row in rows)
    symbol_isins: dict[str, set[str]] = defaultdict(set)
    isin_symbols: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        symbol_isins[row["symbol"]].add(row["isin"])
        isin_symbols[row["isin"]].add(row["symbol"])
    return {
        "row_count": len(rows),
        "unique_identity_count": len(identity_counts),
        "duplicate_identity_count": sum(
            count > 1 for count in identity_counts.values()
        ),
        "symbol_conflict_count": sum(
            len(values) > 1 for values in symbol_isins.values()
        ),
        "isin_conflict_count": sum(
            len(values) > 1 for values in isin_symbols.values()
        ),
        "industry_coverage": (
            0.0
            if not rows
            else sum(bool(row["industry"]) for row in rows) / len(rows)
        ),
        "isin_coverage": (
            0.0
            if not rows
            else sum(bool(row["isin"]) for row in rows) / len(rows)
        ),
        "identity_text_complete": all(
            row["company_name"] and row["symbol"] for row in rows
        ),
    }


def build_industry_snapshot(
    *,
    constituent_raw: bytes,
    security_raw: bytes,
    target_session_date: str,
    captured_at_utc: str,
    constituent_raw_path: str,
    security_raw_path: str,
) -> dict[str, Any]:
    parent = parse_constituent_csv(constituent_raw)
    parent_rows = parent["rows"]
    security_rows, security_diagnostics = parse_security_master_all_series(
        security_raw
    )

    by_triplet: dict[
        tuple[str, str, str], list[dict[str, str]]
    ] = defaultdict(list)
    by_identity: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in security_rows:
        by_triplet[(row["symbol"], row["isin"], row["series"])].append(row)
        by_identity[(row["symbol"], row["isin"])].append(row)

    mapped_eq = []
    dummies = []
    eq_missing = []
    eq_ambiguous = []
    non_eq_matched = 0
    non_eq_missing = []
    non_eq_ambiguous = []
    deletion_flag_conflicts = []

    for row in parent_rows:
        triplet = (row["symbol"], row["isin"], row["series"])
        identity = (row["symbol"], row["isin"])
        exact = by_triplet.get(triplet, [])

        if row["series"] == "EQ":
            if len(exact) == 1:
                security = exact[0]
                if security["deletion_flag"].upper() not in ALLOWED_DELETION_FLAGS:
                    deletion_flag_conflicts.append(
                        {
                            "symbol": row["symbol"],
                            "isin": row["isin"],
                            "deletion_flag": security["deletion_flag"],
                        }
                    )
                mapped_eq.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "company_name": row["company_name"],
                        "industry": row["industry"],
                        "parent_series": row["series"],
                        "security_series": security["series"],
                        "security_name": security["security_name"],
                        "deletion_flag": security["deletion_flag"],
                    }
                )
                continue
            if len(exact) > 1:
                eq_ambiguous.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "series": row["series"],
                        "security_match_count": len(exact),
                    }
                )
                continue

            identity_matches = by_identity.get(identity, [])
            if (
                row["symbol"].startswith("DUMMY")
                and not identity_matches
            ):
                dummies.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "company_name": row["company_name"],
                        "industry": row["industry"],
                        "series": row["series"],
                    }
                )
            else:
                eq_missing.append(
                    {
                        "symbol": row["symbol"],
                        "isin": row["isin"],
                        "series": row["series"],
                        "same_identity_any_series_match_count": len(
                            identity_matches
                        ),
                        "same_identity_series": sorted(
                            {match["series"] for match in identity_matches}
                        ),
                    }
                )
            continue

        if len(exact) == 1:
            non_eq_matched += 1
        elif len(exact) > 1:
            non_eq_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "security_match_count": len(exact),
                }
            )
        else:
            non_eq_missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )

    projected = _identity_diagnostics(mapped_eq)
    eq_parent_count = sum(row["series"] == "EQ" for row in parent_rows)
    non_eq_parent_count = len(parent_rows) - eq_parent_count
    non_eq_match_fraction = (
        0.0
        if non_eq_parent_count == 0
        else non_eq_matched / non_eq_parent_count
    )
    ordinary_eq_match_fraction = (
        0.0
        if not mapped_eq and not eq_missing and not eq_ambiguous
        else (
            len(mapped_eq)
            / (len(mapped_eq) + len(eq_missing) + len(eq_ambiguous))
        )
    )

    gates = {
        "minimum_parent_rows": len(parent_rows) >= MIN_PARENT_ROWS,
        "ordinary_eq_exact_match_fraction_100pct": (
            ordinary_eq_match_fraction == 1.0
        ),
        "ordinary_eq_missing_count_zero": len(eq_missing) == 0,
        "ordinary_eq_ambiguous_count_zero": len(eq_ambiguous) == 0,
        "non_eq_exact_match_fraction_100pct": (
            non_eq_match_fraction == 1.0
        ),
        "non_eq_missing_count_zero": len(non_eq_missing) == 0,
        "non_eq_ambiguous_count_zero": len(non_eq_ambiguous) == 0,
        "minimum_projected_tradable_eq_rows": (
            projected["row_count"] >= MIN_PROJECTED_EQ_ROWS
        ),
        "projected_identity_unique": (
            projected["duplicate_identity_count"] == 0
        ),
        "projected_zero_symbol_conflicts": (
            projected["symbol_conflict_count"] == 0
        ),
        "projected_zero_isin_conflicts": (
            projected["isin_conflict_count"] == 0
        ),
        "projected_industry_coverage_100pct": (
            projected["industry_coverage"] == 1.0
        ),
        "projected_isin_coverage_100pct": (
            projected["isin_coverage"] == 1.0
        ),
        "projected_identity_text_complete": (
            projected["identity_text_complete"]
        ),
        "projected_deletion_flags_allowed": (
            len(deletion_flag_conflicts) == 0
        ),
    }
    ready = all(gates.values())

    mapping_rows = sorted(
        mapped_eq,
        key=lambda row: (row["symbol"], row["isin"]),
    )
    mapping_sha = digest(mapping_rows)

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "snapshot_id": "RM001-SC002-INDUSTRY-SNAPSHOT-v1",
        "status": "READY" if ready else "SEMANTICS_INELIGIBLE",
        "captured_at_utc": captured_at_utc,
        "target_security_session_date": target_session_date,
        "constituent_source": {
            "url": CONSTITUENT_SOURCE_URL,
            "raw_sha256": sha256_bytes(constituent_raw),
            "raw_path": constituent_raw_path,
            "row_count": len(parent_rows),
        },
        "security_source": {
            "raw_sha256": sha256_bytes(security_raw),
            "raw_path": security_raw_path,
            "parsed_row_count": len(security_rows),
            "symbol_isin_duplicate_count": security_diagnostics[
                "duplicate_identity_count"
            ],
        },
        "semantics": {
            "parent_eq_row_count": eq_parent_count,
            "parent_non_eq_row_count": non_eq_parent_count,
            "mapped_eq_count": len(mapped_eq),
            "dummy_count": len(dummies),
            "eq_missing_count": len(eq_missing),
            "eq_ambiguous_count": len(eq_ambiguous),
            "non_eq_matched_count": non_eq_matched,
            "non_eq_missing_count": len(non_eq_missing),
            "non_eq_ambiguous_count": len(non_eq_ambiguous),
            "deletion_flag_conflict_count": len(
                deletion_flag_conflicts
            ),
            "dummies": sorted(
                dummies,
                key=lambda row: (row["symbol"], row["isin"]),
            ),
            "eq_missing": eq_missing[:25],
            "eq_ambiguous": eq_ambiguous[:25],
            "non_eq_missing": non_eq_missing[:25],
            "non_eq_ambiguous": non_eq_ambiguous[:25],
            "deletion_flag_conflicts": deletion_flag_conflicts[:25],
        },
        "projected_tradable_eq": projected,
        "promotion_gates": gates,
        "mapping_sha256": mapping_sha,
        "mapping_rows": mapping_rows,
        "information_effective_no_earlier_than_utc": captured_at_utc,
        "historical_backfill_allowed": False,
        "risk_model_fit_allowed": False,
        "live_capital_allowed": False,
    }
    snapshot["snapshot_sha256"] = digest(snapshot)
    return snapshot


def mapping_change_diagnostics(
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
) -> dict[str, Any]:
    current_rows = {
        (row["symbol"], row["isin"]): row
        for row in current_snapshot.get("mapping_rows", [])
    }
    if previous_snapshot is None:
        return {
            "previous_snapshot_sha256": None,
            "added_identity_count": len(current_rows),
            "removed_identity_count": 0,
            "unchanged_identity_count": 0,
            "industry_changed_identity_count": 0,
            "added_identities": [
                {"symbol": key[0], "isin": key[1]}
                for key in sorted(current_rows)
            ][:25],
            "removed_identities": [],
            "industry_changes": [],
            "dummy_count_change": None,
            "mapping_sha_changed": True,
        }

    previous_rows = {
        (row["symbol"], row["isin"]): row
        for row in previous_snapshot.get("mapping_rows", [])
    }
    current_ids = set(current_rows)
    previous_ids = set(previous_rows)
    added = sorted(current_ids - previous_ids)
    removed = sorted(previous_ids - current_ids)
    common = sorted(current_ids & previous_ids)
    industry_changes = [
        {
            "symbol": identity[0],
            "isin": identity[1],
            "previous_industry": previous_rows[identity]["industry"],
            "current_industry": current_rows[identity]["industry"],
        }
        for identity in common
        if previous_rows[identity]["industry"]
        != current_rows[identity]["industry"]
    ]
    unchanged = sum(
        previous_rows[identity]["industry"]
        == current_rows[identity]["industry"]
        for identity in common
    )
    previous_dummy = int(
        previous_snapshot.get("semantics", {}).get("dummy_count", 0)
    )
    current_dummy = int(
        current_snapshot.get("semantics", {}).get("dummy_count", 0)
    )
    return {
        "previous_snapshot_sha256": previous_snapshot.get(
            "snapshot_sha256"
        ),
        "added_identity_count": len(added),
        "removed_identity_count": len(removed),
        "unchanged_identity_count": unchanged,
        "industry_changed_identity_count": len(industry_changes),
        "added_identities": [
            {"symbol": key[0], "isin": key[1]} for key in added[:25]
        ],
        "removed_identities": [
            {"symbol": key[0], "isin": key[1]} for key in removed[:25]
        ],
        "industry_changes": industry_changes[:25],
        "dummy_count_change": current_dummy - previous_dummy,
        "mapping_sha_changed": (
            previous_snapshot.get("mapping_sha256")
            != current_snapshot.get("mapping_sha256")
        ),
    }


def append_industry_attempt(
    ledger: dict[str, Any],
    *,
    observation_date: str,
    target_session_date: str,
    captured_at_utc: str,
    constituent_status: str,
    constituent_raw_sha256: str | None,
    constituent_raw_path: str | None,
    security_status: str,
    security_raw_sha256: str | None,
    security_raw_path: str | None,
    snapshot: dict[str, Any] | None,
    snapshot_path: str | None,
    change_diagnostics: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_industry_source_ledger(ledger)
    observation = date.fromisoformat(observation_date)
    if observation < START_OBSERVATION_DATE:
        raise AlphaContractError(
            "RM001-SC002 observation precedes frozen start date"
        )

    duplicate = any(
        attempt.get("observation_date") == observation_date
        and attempt.get("target_session_date") == target_session_date
        and attempt.get("constituent_raw_sha256")
        == constituent_raw_sha256
        and attempt.get("security_raw_sha256") == security_raw_sha256
        for attempt in ledger["attempts"]
    )
    if duplicate:
        return copy.deepcopy(ledger), None

    status = (
        "READY"
        if snapshot is not None and snapshot.get("status") == "READY"
        else (
            "SOURCE_UNAVAILABLE"
            if constituent_status == "UNAVAILABLE"
            or security_status == "UNAVAILABLE"
            else (
                "PARSER_REJECTED"
                if constituent_status == "PARSER_REJECTED"
                or security_status == "PARSER_REJECTED"
                else "SEMANTICS_INELIGIBLE"
            )
        )
    )
    attempt: dict[str, Any] = {
        "seq": len(ledger["attempts"]) + 1,
        "observation_date": observation_date,
        "target_session_date": target_session_date,
        "captured_at_utc": captured_at_utc,
        "status": status,
        "constituent_status": constituent_status,
        "constituent_raw_sha256": constituent_raw_sha256,
        "constituent_raw_path": constituent_raw_path,
        "security_status": security_status,
        "security_raw_sha256": security_raw_sha256,
        "security_raw_path": security_raw_path,
        "snapshot_sha256": (
            None if snapshot is None else snapshot["snapshot_sha256"]
        ),
        "snapshot_path": snapshot_path,
        "mapping_sha256": (
            None if snapshot is None else snapshot["mapping_sha256"]
        ),
        "mapped_eq_count": (
            None
            if snapshot is None
            else snapshot["semantics"]["mapped_eq_count"]
        ),
        "dummy_count": (
            None
            if snapshot is None
            else snapshot["semantics"]["dummy_count"]
        ),
        "change_diagnostics": change_diagnostics,
        "historical_backfill_allowed": False,
        "risk_model_fit_allowed": False,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    updated["attempts"].append(attempt)
    updated["attempt_count"] = len(updated["attempts"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_industry_source_ledger(updated)
    return updated, attempt


def industry_readiness_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    validate_industry_source_ledger(ledger)
    ready = [
        attempt
        for attempt in ledger["attempts"]
        if attempt.get("status") == "READY"
    ]
    observation_dates = sorted(
        {str(attempt["observation_date"]) for attempt in ready}
    )
    target_sessions = sorted(
        {str(attempt["target_session_date"]) for attempt in ready}
    )
    ready_dates = len(observation_dates)
    ready_targets = len(target_sessions)
    operational_ready = (
        ready_dates >= MIN_READY_OBSERVATION_DATES
        and ready_targets >= MIN_READY_TARGET_SESSIONS
    )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": LEDGER_ID,
        "attempt_count": ledger["attempt_count"],
        "ready_attempt_count": len(ready),
        "distinct_ready_observation_date_count": ready_dates,
        "distinct_ready_target_session_count": ready_targets,
        "minimum_ready_observation_dates": MIN_READY_OBSERVATION_DATES,
        "minimum_ready_target_sessions": MIN_READY_TARGET_SESSIONS,
        "additional_ready_observation_dates_needed": max(
            0,
            MIN_READY_OBSERVATION_DATES - ready_dates,
        ),
        "additional_ready_target_sessions_needed": max(
            0,
            MIN_READY_TARGET_SESSIONS - ready_targets,
        ),
        "prospective_industry_source_capture_ready": operational_ready,
        "latest_ready_attempt_sha256": (
            None if not ready else ready[-1]["attempt_sha256"]
        ),
        "latest_ready_snapshot_sha256": (
            None if not ready else ready[-1]["snapshot_sha256"]
        ),
        "factor_automatically_enabled": False,
        "historical_backfill_allowed": False,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = digest(summary)
    return summary
