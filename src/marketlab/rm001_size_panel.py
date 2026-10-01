from __future__ import annotations

import math
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes
from marketlab.marketdata import MarketArtifactStore
from marketlab.rm001_size_source import (
    D007_MIN_DAILY_ISSUED_SIZE_COVERAGE,
    D007_MIN_DAILY_JOIN_COVERAGE,
    parse_security_master_eq,
    security_master_url,
)

RM001_V2_SIZE_PANEL_ID = "RM001-v2-SIZE-PANEL-v1"
D007_RESULT_SHA256 = (
    "4151612cb85c88d605344fd018fab85118c295e71a90fabbe6c2223d15f27c14"
)


def _verify_hash(payload: dict[str, Any], *, field: str, name: str) -> None:
    stored = str(payload.get(field) or "")
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def _market_identity_map(
    session: dict[str, Any],
) -> dict[tuple[str, str], DailyEquityObservation]:
    result: dict[tuple[str, str], DailyEquityObservation] = {}
    for raw in session.get("equities", []):
        row = (
            raw
            if isinstance(raw, DailyEquityObservation)
            else DailyEquityObservation(**raw)
        )
        if row.isin.upper().startswith("DUMMY"):
            continue
        identity = (row.symbol, row.isin)
        if identity in result:
            raise AlphaContractError(
                f"{session['session_date']}: duplicate RM001-v2 market identity"
            )
        result[identity] = row
    return result


def build_rm001_v2_size_panel(
    *,
    market_panel: dict[str, Any],
    fetcher,
    store_root: str | Path | None = None,
    captured_at_utc: datetime | None = None,
) -> dict[str, Any]:
    _verify_hash(
        market_panel,
        field="panel_sha256",
        name="RM001-v2 market panel",
    )
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("RM001-v2 market sessions are required")
    captured = captured_at_utc or datetime.now(UTC)
    if captured.tzinfo is None:
        raise AlphaContractError(
            "RM001-v2 size capture timestamp must be timezone-aware"
        )
    store = MarketArtifactStore(store_root) if store_root is not None else None

    panel_sessions = []
    total_rows = 0
    minimum_join_coverage = 1.0

    for market_session in sessions:
        session_text = str(market_session["session_date"])
        day = date.fromisoformat(session_text)
        url = security_master_url(day)
        raw = fetcher(url)
        if raw is None:
            raise AlphaContractError(
                f"{session_text}: RM001-v2 Security File unavailable"
            )
        raw_sha = sha256_bytes(raw)
        if store is not None:
            store.retain(
                raw,
                source_url=url,
                captured_at=captured,
                suffix=".csv.gz",
            )
        rows, diagnostics = parse_security_master_eq(
            raw,
            session_date=day,
        )
        if diagnostics["duplicate_real_eq_identity_count"] != 0:
            raise AlphaContractError(
                f"{session_text}: duplicate Security File identities"
            )

        market = _market_identity_map(market_session)
        security = {(row.symbol, row.isin): row for row in rows}
        common = sorted(set(market) & set(security))
        market_count = len(market)
        coverage = 1.0 if market_count == 0 else len(common) / market_count
        minimum_join_coverage = min(minimum_join_coverage, coverage)
        if coverage < D007_MIN_DAILY_JOIN_COVERAGE:
            raise AlphaContractError(
                f"{session_text}: RM001-v2 size join coverage below D007 gate"
            )

        size_rows = []
        issued_ready = 0
        market_cap_ready = 0
        for identity in common:
            source = security[identity]
            if source.issued_size is None:
                continue
            issued_ready += 1
            cap = market[identity].close_price * source.issued_size
            if not math.isfinite(cap) or cap <= 0:
                continue
            market_cap_ready += 1
            size_rows.append(
                {
                    "symbol": identity[0],
                    "isin": identity[1],
                    "issued_size": source.issued_size,
                    "official_close": market[identity].close_price,
                    "total_market_cap_inr": cap,
                }
            )

        joined_count = len(common)
        issued_coverage = (
            1.0 if joined_count == 0 else issued_ready / joined_count
        )
        market_cap_coverage = (
            1.0 if joined_count == 0 else market_cap_ready / joined_count
        )
        if (
            issued_coverage < D007_MIN_DAILY_ISSUED_SIZE_COVERAGE
            or market_cap_coverage < D007_MIN_DAILY_ISSUED_SIZE_COVERAGE
        ):
            raise AlphaContractError(
                f"{session_text}: RM001-v2 positive size coverage below D007 gate"
            )

        size_rows.sort(key=lambda row: (row["symbol"], row["isin"]))
        total_rows += len(size_rows)
        session_record = {
            "session_date": session_text,
            "source_url": url,
            "raw_sha256": raw_sha,
            "market_eq_identity_count": market_count,
            "exact_joined_identity_count": joined_count,
            "exact_join_coverage": coverage,
            "positive_issued_size_coverage": issued_coverage,
            "positive_market_cap_coverage": market_cap_coverage,
            "rows": size_rows,
        }
        session_record["session_sha256"] = digest(session_record)
        panel_sessions.append(session_record)

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": RM001_V2_SIZE_PANEL_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "market_panel_sha256": market_panel["panel_sha256"],
        "d007_result_sha256": D007_RESULT_SHA256,
        "size_formula": "TOTAL_MARKET_CAP_INR = OFFICIAL_CLOSE * ISSD_CPTL",
        "session_count": len(panel_sessions),
        "row_count": total_rows,
        "minimum_exact_join_coverage": minimum_join_coverage,
        "sessions": panel_sessions,
        "prospective_source_timing_verified": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def size_rows_by_session(
    size_panel: dict[str, Any],
) -> dict[str, dict[tuple[str, str], float]]:
    _verify_hash(
        size_panel,
        field="panel_sha256",
        name="RM001-v2 size panel",
    )
    if size_panel.get("panel_id") != RM001_V2_SIZE_PANEL_ID:
        raise AlphaContractError("unexpected RM001-v2 size panel identity")
    result: dict[str, dict[tuple[str, str], float]] = {}
    for session in size_panel.get("sessions", []):
        day = str(session["session_date"])
        rows = {}
        for raw in session.get("rows", []):
            identity = (str(raw["symbol"]), str(raw["isin"]))
            if identity in rows:
                raise AlphaContractError(
                    f"{day}: duplicate RM001-v2 size identity"
                )
            value = float(raw["total_market_cap_inr"])
            if not math.isfinite(value) or value <= 0:
                raise AlphaContractError(
                    f"{day}: invalid RM001-v2 total market cap"
                )
            rows[identity] = value
        result[day] = rows
    return result
