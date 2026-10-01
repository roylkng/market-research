from __future__ import annotations

import copy
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p3 import (
    map_source_rows,
    parse_short_selling,
    parse_slb_open_positions,
)
from marketlab.alpha_d010_p3b import map_lagged_short_rows
from marketlab.alpha_market import DailyEquityObservation, parse_udiff_eq_panel
from marketlab.events import sha256_bytes

SC004_LEDGER_ID = "AE001-SC004-SOURCE-LEDGER-v1"
SC004_START_DATE = date(2026, 10, 2)
IST = ZoneInfo("Asia/Kolkata")
DECISION_CUTOFF = time(18, 30)
MAX_PREVIOUS_SESSION_LOOKBACK_DAYS = 7
MIN_SHORT_MAPPING_FRACTION = 0.95
MIN_SHORT_CONTINUITY_FRACTION = 0.95
MIN_SLB_MAPPING_FRACTION = 0.95
RAW_ROOT_REPO = "research/prospective/ae001-sc004/raw"


def _ledger_hash(ledger: dict[str, Any]) -> str:
    unsigned = copy.deepcopy(ledger)
    unsigned.pop("ledger_sha256", None)
    return digest(unsigned)


def new_sc004_source_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "ledger_id": SC004_LEDGER_ID,
        "attempt_count": 0,
        "attempts": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = _ledger_hash(ledger)
    return ledger


def validate_sc004_source_ledger(ledger: dict[str, Any]) -> None:
    if ledger.get("ledger_id") != SC004_LEDGER_ID:
        raise AlphaContractError("unexpected SC004 source ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("SC004 cannot allow live capital")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        raise AlphaContractError("SC004 attempts must be a list")
    if ledger.get("attempt_count") != len(attempts):
        raise AlphaContractError("SC004 attempt count mismatch")
    seen_sessions = []
    for index, attempt in enumerate(attempts, start=1):
        if attempt.get("seq") != index:
            raise AlphaContractError("SC004 attempt sequence mismatch")
        stored = str(attempt.get("attempt_sha256") or "")
        unsigned = copy.deepcopy(attempt)
        unsigned.pop("attempt_sha256", None)
        if stored != digest(unsigned):
            raise AlphaContractError("SC004 attempt hash mismatch")
        publication = str(attempt.get("publication_session") or "")
        if not publication:
            raise AlphaContractError("SC004 attempt lacks publication session")
        seen_sessions.append(publication)
    if str(ledger.get("ledger_sha256") or "") != _ledger_hash(ledger):
        raise AlphaContractError("SC004 ledger hash mismatch")


def decision_cutoff_utc(session_date: str) -> datetime:
    day = date.fromisoformat(session_date)
    return datetime.combine(day, DECISION_CUTOFF, IST).astimezone(UTC)


def session_already_eligible(
    ledger: dict[str, Any],
    session_date: str,
) -> bool:
    validate_sc004_source_ledger(ledger)
    return any(
        attempt.get("publication_session") == session_date
        and attempt.get("eligible_before_cutoff") is True
        for attempt in ledger["attempts"]
    )


def _market_observation(
    raw: bytes | None,
    *,
    session_date: date,
    source_url: str,
    role: str,
) -> tuple[dict[str, Any], list[DailyEquityObservation] | None]:
    if raw is None:
        return (
            {
                "role": role,
                "session_date": session_date.isoformat(),
                "source_url": source_url,
                "status": "UNAVAILABLE",
                "raw_sha256": None,
                "raw_repo_path": None,
                "eq_row_count": None,
            },
            None,
        )
    raw_sha = sha256_bytes(raw)
    label = "current-market" if role == "PUBLICATION_SESSION" else "previous-market"
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{{publication_session}}/"
        f"{label}-{session_date.isoformat()}-{raw_sha}.zip"
    )
    try:
        rows = parse_udiff_eq_panel(raw, session_date=session_date)
    except AlphaContractError as exc:
        return (
            {
                "role": role,
                "session_date": session_date.isoformat(),
                "source_url": source_url,
                "status": "PARSER_REJECTED",
                "raw_sha256": raw_sha,
                "raw_repo_path_template": raw_repo_path,
                "eq_row_count": None,
                "error": str(exc),
            },
            None,
        )
    return (
        {
            "role": role,
            "session_date": session_date.isoformat(),
            "source_url": source_url,
            "status": "READY",
            "raw_sha256": raw_sha,
            "raw_repo_path_template": raw_repo_path,
            "eq_row_count": len(rows),
        },
        rows,
    )


def _short_observation(
    raw: bytes | None,
    *,
    publication_session: date,
    previous_session: date | None,
    previous_equities: list[DailyEquityObservation] | None,
    publication_equities: list[DailyEquityObservation] | None,
    source_url: str,
) -> dict[str, Any]:
    if raw is None:
        return {
            "source_url": source_url,
            "status": "UNAVAILABLE",
            "raw_sha256": None,
            "raw_repo_path": None,
            "source_row_count": None,
            "identity_mapping_fraction": None,
            "publication_isin_continuity_fraction": None,
            "identity_gate_pass": False,
        }

    raw_sha = sha256_bytes(raw)
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{publication_session.isoformat()}/"
        f"short-{raw_sha}.csv.gz"
    )
    if previous_session is None:
        return {
            "source_url": source_url,
            "status": "DEPENDENCY_NOT_READY",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "source_row_count": None,
            "identity_mapping_fraction": None,
            "publication_isin_continuity_fraction": None,
            "identity_gate_pass": False,
        }

    try:
        rows, schema = parse_short_selling(
            raw,
            session_date=previous_session,
        )
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "source_row_count": None,
            "identity_mapping_fraction": None,
            "publication_isin_continuity_fraction": None,
            "identity_gate_pass": False,
            "error": str(exc),
        }

    if previous_equities is None or publication_equities is None:
        return {
            "source_url": source_url,
            "status": "IDENTITY_DEPENDENCY_NOT_READY",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "schema": list(schema),
            "source_row_count": len(rows),
            "identity_mapping_fraction": None,
            "publication_isin_continuity_fraction": None,
            "identity_gate_pass": False,
        }

    mapped = map_lagged_short_rows(
        publication_session=publication_session.isoformat(),
        trade_session=previous_session.isoformat(),
        rows=rows,
        trade_date_equities=previous_equities,
        publication_equities=publication_equities,
        raw_sha256=raw_sha,
        source_status="READY",
    )
    source_count = int(mapped["source_row_count"])
    mapped_count = int(mapped["trade_date_mapped_row_count"])
    continuity_count = int(mapped["publication_continuity_row_count"])
    mapping_fraction = (
        1.0 if source_count == 0 else mapped_count / source_count
    )
    continuity_fraction = (
        1.0 if mapped_count == 0 else continuity_count / mapped_count
    )
    duplicate_count = int(mapped["duplicate_symbol_row_count"])
    identity_pass = (
        duplicate_count == 0
        and mapping_fraction >= MIN_SHORT_MAPPING_FRACTION
        and continuity_fraction >= MIN_SHORT_CONTINUITY_FRACTION
    )
    return {
        "source_url": source_url,
        "status": "READY" if identity_pass else "IDENTITY_GATE_FAILED",
        "raw_sha256": raw_sha,
        "raw_repo_path": raw_repo_path,
        "schema": list(schema),
        "source_row_count": source_count,
        "trade_date_mapped_row_count": mapped_count,
        "publication_continuity_row_count": continuity_count,
        "duplicate_symbol_row_count": duplicate_count,
        "identity_mapping_fraction": mapping_fraction,
        "publication_isin_continuity_fraction": continuity_fraction,
        "identity_gate_pass": identity_pass,
    }


def _slb_observation(
    raw: bytes | None,
    *,
    publication_session: date,
    publication_equities: list[DailyEquityObservation] | None,
    source_url: str,
) -> dict[str, Any]:
    if raw is None:
        return {
            "source_url": source_url,
            "status": "UNAVAILABLE",
            "raw_sha256": None,
            "raw_repo_path": None,
            "source_row_count": None,
            "identity_mapping_fraction": None,
            "identity_gate_pass": False,
        }

    raw_sha = sha256_bytes(raw)
    raw_repo_path = (
        f"{RAW_ROOT_REPO}/{publication_session.isoformat()}/"
        f"slb-{raw_sha}.csv.gz"
    )
    try:
        rows, schema = parse_slb_open_positions(raw)
    except AlphaContractError as exc:
        return {
            "source_url": source_url,
            "status": "PARSER_REJECTED",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "source_row_count": None,
            "identity_mapping_fraction": None,
            "identity_gate_pass": False,
            "error": str(exc),
        }

    if publication_equities is None:
        return {
            "source_url": source_url,
            "status": "IDENTITY_DEPENDENCY_NOT_READY",
            "raw_sha256": raw_sha,
            "raw_repo_path": raw_repo_path,
            "schema": list(schema),
            "source_row_count": len(rows),
            "identity_mapping_fraction": None,
            "identity_gate_pass": False,
        }

    mapped = map_source_rows(
        short_rows=None,
        slb_rows=rows,
        equities=publication_equities,
        session_date=publication_session.isoformat(),
        short_raw_sha256=None,
        slb_raw_sha256=raw_sha,
    )["slb_open_positions"]
    source_count = int(mapped["row_count"])
    mapped_count = int(mapped["mapped_row_count"])
    mapping_fraction = (
        1.0 if source_count == 0 else mapped_count / source_count
    )
    duplicate_symbol_series_count = int(
        mapped["duplicate_symbol_series_row_count"]
    )
    identity_pass = (
        duplicate_symbol_series_count == 0
        and mapping_fraction >= MIN_SLB_MAPPING_FRACTION
    )
    return {
        "source_url": source_url,
        "status": "READY" if identity_pass else "IDENTITY_GATE_FAILED",
        "raw_sha256": raw_sha,
        "raw_repo_path": raw_repo_path,
        "schema": list(schema),
        "source_row_count": source_count,
        "mapped_row_count": mapped_count,
        "duplicate_symbol_row_count": int(
            mapped["duplicate_symbol_row_count"]
        ),
        "duplicate_symbol_series_row_count": duplicate_symbol_series_count,
        "identity_mapping_fraction": mapping_fraction,
        "identity_gate_pass": identity_pass,
    }


def append_sc004_source_probe(
    ledger: dict[str, Any],
    *,
    publication_session: str,
    previous_completed_session: str | None,
    captured_at_utc: str,
    current_market_source_url: str,
    current_market_raw: bytes | None,
    previous_market_source_url: str | None,
    previous_market_raw: bytes | None,
    short_source_url: str,
    short_raw: bytes | None,
    slb_source_url: str,
    slb_raw: bytes | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    validate_sc004_source_ledger(ledger)
    day = date.fromisoformat(publication_session)
    if day < SC004_START_DATE:
        raise AlphaContractError("SC004 probe precedes frozen start boundary")
    if session_already_eligible(ledger, publication_session):
        return copy.deepcopy(ledger), None

    previous_day = (
        None
        if previous_completed_session is None
        else date.fromisoformat(previous_completed_session)
    )
    if previous_day is not None:
        delta = (day - previous_day).days
        if delta < 1 or delta > MAX_PREVIOUS_SESSION_LOOKBACK_DAYS:
            raise AlphaContractError(
                "SC004 previous completed session violates frozen lookback"
            )

    try:
        captured = datetime.fromisoformat(captured_at_utc)
    except ValueError as exc:
        raise AlphaContractError("SC004 capture timestamp is invalid") from exc
    if captured.tzinfo is None:
        raise AlphaContractError("SC004 capture timestamp must be timezone-aware")
    captured = captured.astimezone(UTC)
    cutoff = decision_cutoff_utc(publication_session)

    current_market, current_equities = _market_observation(
        current_market_raw,
        session_date=day,
        source_url=current_market_source_url,
        role="PUBLICATION_SESSION",
    )
    current_path_template = current_market.pop(
        "raw_repo_path_template",
        None,
    )
    if current_path_template is not None:
        current_market["raw_repo_path"] = current_path_template.format(
            publication_session=publication_session
        )

    previous_market: dict[str, Any]
    previous_equities: list[DailyEquityObservation] | None
    if previous_day is None:
        previous_market = {
            "role": "PREVIOUS_COMPLETED_SESSION",
            "session_date": None,
            "source_url": previous_market_source_url,
            "status": "UNRESOLVED",
            "raw_sha256": None,
            "raw_repo_path": None,
            "eq_row_count": None,
        }
        previous_equities = None
    else:
        previous_market, previous_equities = _market_observation(
            previous_market_raw,
            session_date=previous_day,
            source_url=str(previous_market_source_url or ""),
            role="PREVIOUS_COMPLETED_SESSION",
        )
        previous_path_template = previous_market.pop(
            "raw_repo_path_template",
            None,
        )
        if previous_path_template is not None:
            previous_market["raw_repo_path"] = previous_path_template.format(
                publication_session=publication_session
            )

    short = _short_observation(
        short_raw,
        publication_session=day,
        previous_session=previous_day,
        previous_equities=previous_equities,
        publication_equities=current_equities,
        source_url=short_source_url,
    )
    slb = _slb_observation(
        slb_raw,
        publication_session=day,
        publication_equities=current_equities,
        source_url=slb_source_url,
    )

    eligible = (
        captured <= cutoff
        and current_market["status"] == "READY"
        and previous_market["status"] == "READY"
        and short["status"] == "READY"
        and slb["status"] == "READY"
    )

    updated = copy.deepcopy(ledger)
    updated.pop("ledger_sha256", None)
    attempt: dict[str, Any] = {
        "seq": len(updated["attempts"]) + 1,
        "publication_session": publication_session,
        "previous_completed_session": (
            None if previous_day is None else previous_day.isoformat()
        ),
        "captured_at_utc": captured.isoformat(),
        "decision_cutoff_utc": cutoff.isoformat(),
        "captured_before_or_at_cutoff": captured <= cutoff,
        "current_market": current_market,
        "previous_market": previous_market,
        "short_selling": short,
        "slb_open_positions": slb,
        "eligible_before_cutoff": eligible,
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    attempt["attempt_sha256"] = digest(attempt)
    updated["attempts"].append(attempt)
    updated["attempt_count"] = len(updated["attempts"])
    updated["ledger_sha256"] = _ledger_hash(updated)
    validate_sc004_source_ledger(updated)
    return updated, attempt
