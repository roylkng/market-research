from __future__ import annotations

import copy
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.rm001_d015 import SOURCE_URL, parse_constituent_csv
from marketlab.rm001_d015_r1 import parse_security_master_all_series

LEDGER_ID = "RM001-SC002-INDUSTRY-SOURCE-LEDGER-v1"
START_OBSERVATION_DATE = date(2026, 10, 5)
IST = ZoneInfo("Asia/Kolkata")
DECISION_CUTOFF = time(18, 30)
RAW_ROOT_REPO = "research/prospective/rm001-sc002/raw"
SNAPSHOT_ROOT_REPO = "research/prospective/rm001-sc002/snapshots"
MIN_PARENT_ROWS = 700
MIN_PROJECTED_EQ_ROWS = 700
MIN_INDUSTRY_LABELS = 10
MAX_INDUSTRY_LABELS = 40
MIN_READY_SESSIONS = 3


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
    if int(ledger.get("attempt_count") or 0) != len(attempts):
        raise AlphaContractError("RM001-SC002 attempt count mismatch")

    ready_sessions: set[str] = set()
    for index, attempt in enumerate(attempts, start=1):
        if int(attempt.get("seq") or 0) != index:
            raise AlphaContractError("RM001-SC002 attempt sequence mismatch")
        session = str(attempt.get("session_date") or "")
        if not session:
            raise AlphaContractError("RM001-SC002 attempt lacks session date")
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = copy.deepcopy(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("RM001-SC002 attempt hash mismatch")
        if attempt.get("ready_before_cutoff") is True:
            if attempt.get("source_status") != "READY":
                raise AlphaContractError(
                    "RM001-SC002 ready attempt has non-ready source"
                )
            if session in ready_sessions:
                raise AlphaContractError(
                    "RM001-SC002 contains duplicate ready session"
                )
            ready_sessions.add(session)

    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("RM001-SC002 ledger hash mismatch")


def decision_cutoff_utc(session_date: str) -> datetime:
    day = date.fromisoformat(session_date)
    return datetime.combine(day, DECISION_CUTOFF, IST).astimezone(UTC)


def session_ready_observed(
    ledger: dict[str, Any],
    session_date: str,
) -> bool:
    validate_industry_source_ledger(ledger)
    return any(
        attempt.get("session_date") == session_date
        and attempt.get("ready_before_cutoff") is True
        for attempt in ledger["attempts"]
    )


def _identity_diagnostics(rows: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter((row["symbol"], row["isin"]) for row in rows)
    symbol_isins: dict[str, set[str]] = defaultdict(set)
    isin_symbols: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        symbol_isins[row["symbol"]].add(row["isin"])
        isin_symbols[row["isin"]].add(row["symbol"])
    return {
        "row_count": len(rows),
        "unique_identity_count": len(counts),
        "duplicate_identity_count": sum(count > 1 for count in counts.values()),
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
        "industry_label_count": len(
            {row["industry"] for row in rows if row["industry"]}
        ),
    }


def build_industry_snapshot(
    *,
    session_date: str,
    constituent_raw: bytes,
    security_raw: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    day = date.fromisoformat(session_date)
    if day < START_OBSERVATION_DATE:
        raise AlphaContractError(
            "RM001-SC002 session precedes frozen observation boundary"
        )

    parent = parse_constituent_csv(constituent_raw)
    parent_rows = parent["rows"]
    security_rows, security_diagnostics = parse_security_master_all_series(
        security_raw
    )

    security_by_triplet: dict[
        tuple[str, str, str], list[dict[str, str]]
    ] = defaultdict(list)
    security_by_identity: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in security_rows:
        security_by_triplet[
            (row["symbol"], row["isin"], row["series"])
        ].append(row)
        security_by_identity[(row["symbol"], row["isin"])].append(row)

    parent_eq = [row for row in parent_rows if row["series"] == "EQ"]
    parent_non_eq = [row for row in parent_rows if row["series"] != "EQ"]
    dummy_eq = [
        row for row in parent_eq if row["symbol"].startswith("DUMMY")
    ]
    ordinary_eq = [
        row for row in parent_eq if not row["symbol"].startswith("DUMMY")
    ]

    ordinary_matched: list[dict[str, str]] = []
    ordinary_missing = []
    ordinary_ambiguous = []
    for row in ordinary_eq:
        matches = security_by_triplet.get(
            (row["symbol"], row["isin"], row["series"]),
            [],
        )
        if len(matches) == 1:
            ordinary_matched.append(row)
        elif not matches:
            ordinary_missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )
        else:
            ordinary_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "match_count": len(matches),
                }
            )

    dummy_invalid = []
    dummy_rows = []
    for row in dummy_eq:
        exact = security_by_triplet.get(
            (row["symbol"], row["isin"], row["series"]),
            [],
        )
        same_identity = security_by_identity.get(
            (row["symbol"], row["isin"]),
            [],
        )
        diagnostic = {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "series": row["series"],
            "industry": row["industry"],
            "exact_triplet_match_count": len(exact),
            "same_identity_any_series_match_count": len(same_identity),
        }
        dummy_rows.append(diagnostic)
        if exact or same_identity:
            dummy_invalid.append(diagnostic)

    non_eq_missing = []
    non_eq_ambiguous = []
    non_eq_matched = 0
    for row in parent_non_eq:
        matches = security_by_triplet.get(
            (row["symbol"], row["isin"], row["series"]),
            [],
        )
        if len(matches) == 1:
            non_eq_matched += 1
        elif not matches:
            non_eq_missing.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                }
            )
        else:
            non_eq_ambiguous.append(
                {
                    "symbol": row["symbol"],
                    "isin": row["isin"],
                    "series": row["series"],
                    "match_count": len(matches),
                }
            )

    projected_rows = [
        {
            "symbol": row["symbol"],
            "isin": row["isin"],
            "industry": row["industry"],
            "company_name": row["company_name"],
            "series": "EQ",
        }
        for row in ordinary_matched
    ]
    projected_rows.sort(
        key=lambda row: (row["symbol"], row["isin"])
    )
    projected = _identity_diagnostics(projected_rows)

    gates = {
        "minimum_parent_rows": len(parent_rows) >= MIN_PARENT_ROWS,
        "minimum_projected_eq_rows": (
            projected["row_count"] >= MIN_PROJECTED_EQ_ROWS
        ),
        "ordinary_eq_missing_zero": len(ordinary_missing) == 0,
        "ordinary_eq_ambiguous_zero": len(ordinary_ambiguous) == 0,
        "dummy_semantics_all_valid": len(dummy_invalid) == 0,
        "non_eq_missing_zero": len(non_eq_missing) == 0,
        "non_eq_ambiguous_zero": len(non_eq_ambiguous) == 0,
        "projected_identity_unique": (
            projected["row_count"] == projected["unique_identity_count"]
        ),
        "projected_duplicate_identity_zero": (
            projected["duplicate_identity_count"] == 0
        ),
        "projected_symbol_conflict_zero": (
            projected["symbol_conflict_count"] == 0
        ),
        "projected_isin_conflict_zero": (
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
        "industry_label_count_range": (
            MIN_INDUSTRY_LABELS
            <= projected["industry_label_count"]
            <= MAX_INDUSTRY_LABELS
        ),
    }
    ready = all(gates.values())

    constituent_sha = sha256_bytes(constituent_raw)
    security_sha = sha256_bytes(security_raw)
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "snapshot_id": "RM001-SC002-INDUSTRY-SNAPSHOT-v1",
        "session_date": session_date,
        "constituent_source_url": SOURCE_URL,
        "constituent_raw_sha256": constituent_sha,
        "security_raw_sha256": security_sha,
        "projection_rule": (
            'Series=="EQ" AND NOT Symbol.startswith("DUMMY") '
            "AND exact same-snapshot Symbol+ISIN+Series match"
        ),
        "row_count": len(projected_rows),
        "industry_label_count": projected["industry_label_count"],
        "rows": projected_rows,
        "return_labels_attached": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    snapshot["snapshot_sha256"] = digest(snapshot)

    diagnostics = {
        "source_status": "READY" if ready else "SEMANTIC_QUALITY_REJECTED",
        "parent_row_count": len(parent_rows),
        "parent_eq_row_count": len(parent_eq),
        "parent_non_eq_row_count": len(parent_non_eq),
        "ordinary_eq_row_count": len(ordinary_eq),
        "ordinary_eq_matched_count": len(ordinary_matched),
        "ordinary_eq_missing_count": len(ordinary_missing),
        "ordinary_eq_ambiguous_count": len(ordinary_ambiguous),
        "ordinary_eq_missing": ordinary_missing[:25],
        "ordinary_eq_ambiguous": ordinary_ambiguous[:25],
        "dummy_eq_row_count": len(dummy_eq),
        "dummy_invalid_count": len(dummy_invalid),
        "dummy_rows": sorted(
            dummy_rows,
            key=lambda row: (row["symbol"], row["isin"]),
        ),
        "non_eq_row_count": len(parent_non_eq),
        "non_eq_matched_count": non_eq_matched,
        "non_eq_missing_count": len(non_eq_missing),
        "non_eq_ambiguous_count": len(non_eq_ambiguous),
        "projected": projected,
        "security_parsed_row_count": security_diagnostics[
            "parsed_row_count"
        ],
        "security_series_counts": security_diagnostics["series_counts"],
        "gates": gates,
    }
    return snapshot, diagnostics


def append_industry_source_probe(
    ledger: dict[str, Any],
    *,
    session_date: str,
    captured_at_utc: str,
    constituent_raw: bytes | None,
    security_raw: bytes | None,
    security_source_url: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    validate_industry_source_ledger(ledger)
    day = date.fromisoformat(session_date)
    if day < START_OBSERVATION_DATE:
        raise AlphaContractError(
            "RM001-SC002 session precedes frozen observation boundary"
        )
    if session_ready_observed(ledger, session_date):
        return copy.deepcopy(ledger), None, None

    try:
        captured = datetime.fromisoformat(captured_at_utc)
    except ValueError as exc:
        raise AlphaContractError(
            "RM001-SC002 capture timestamp is invalid"
        ) from exc
    if captured.tzinfo is None:
        raise AlphaContractError(
            "RM001-SC002 capture timestamp must be timezone-aware"
        )
    captured = captured.astimezone(UTC)
    cutoff = decision_cutoff_utc(session_date)

    constituent_sha = (
        None if constituent_raw is None else sha256_bytes(constituent_raw)
    )
    security_sha = (
        None if security_raw is None else sha256_bytes(security_raw)
    )
    constituent_path = (
        None
        if constituent_sha is None
        else (
            f"{RAW_ROOT_REPO}/{session_date}/"
            f"nifty-total-market-{constituent_sha}.csv"
        )
    )
    security_path = (
        None
        if security_sha is None
        else (
            f"{RAW_ROOT_REPO}/{session_date}/"
            f"security-{security_sha}.csv.gz"
        )
    )

    snapshot = None
    diagnostics: dict[str, Any] | None = None
    if constituent_raw is None or security_raw is None:
        status = "UNAVAILABLE"
    else:
        try:
            snapshot, diagnostics = build_industry_snapshot(
                session_date=session_date,
                constituent_raw=constituent_raw,
                security_raw=security_raw,
            )
            status = str(diagnostics["source_status"])
        except AlphaContractError as exc:
            status = "PARSER_REJECTED"
            diagnostics = {"error": str(exc)}

    ready_before_cutoff = (
        status == "READY" and captured <= cutoff
    )
    snapshot_path = (
        None
        if snapshot is None
        else f"{SNAPSHOT_ROOT_REPO}/{session_date}-v1.json.gz"
    )

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    attempt: dict[str, Any] = {
        "seq": len(updated["attempts"]) + 1,
        "session_date": session_date,
        "captured_at_utc": captured.isoformat(),
        "decision_cutoff_utc": cutoff.isoformat(),
        "captured_before_or_at_cutoff": captured <= cutoff,
        "constituent_source_url": SOURCE_URL,
        "constituent_raw_sha256": constituent_sha,
        "constituent_raw_repo_path": constituent_path,
        "security_source_url": security_source_url,
        "security_raw_sha256": security_sha,
        "security_raw_repo_path": security_path,
        "source_status": status,
        "ready_before_cutoff": ready_before_cutoff,
        "industry_snapshot_sha256": (
            None if snapshot is None else snapshot["snapshot_sha256"]
        ),
        "industry_snapshot_repo_path": snapshot_path,
        "projected_eq_row_count": (
            None if snapshot is None else snapshot["row_count"]
        ),
        "industry_label_count": (
            None if snapshot is None else snapshot["industry_label_count"]
        ),
        "diagnostics": diagnostics,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    updated["attempts"].append(attempt)
    updated["attempt_count"] = len(updated["attempts"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_industry_source_ledger(updated)
    return updated, attempt, snapshot


def industry_readiness_summary(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    validate_industry_source_ledger(ledger)
    ready = sorted(
        {
            str(attempt["session_date"])
            for attempt in ledger["attempts"]
            if attempt.get("ready_before_cutoff") is True
        }
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "analysis_id": "RM001-SC002-INDUSTRY-READINESS-v1",
        "source_ledger_sha256": ledger["ledger_sha256"],
        "ready_before_cutoff_sessions": ready,
        "ready_before_cutoff_session_count": len(ready),
        "minimum_ready_sessions_for_factor_design": MIN_READY_SESSIONS,
        "additional_ready_sessions_needed": max(
            0,
            MIN_READY_SESSIONS - len(ready),
        ),
        "prospective_industry_source_ready": (
            len(ready) >= MIN_READY_SESSIONS
        ),
        "historical_backfill_allowed": False,
        "industry_factor_enabled": False,
        "return_labels_opened": False,
        "live_capital_allowed": False,
    }
    result["summary_sha256"] = digest(result)
    return result
