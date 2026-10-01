from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p3 import ShortSellingRow
from marketlab.alpha_market import DailyEquityObservation

D010_P3B_ID = "AE001-D010-P3B-v1"
MIN_READY_SESSION_FRACTION = 0.95
MIN_TRADE_DATE_MAPPING_FRACTION = 0.95
MIN_PUBLICATION_CONTINUITY_FRACTION = 0.95


def map_lagged_short_rows(
    *,
    publication_session: str,
    trade_session: str,
    rows: list[ShortSellingRow] | None,
    trade_date_equities: list[DailyEquityObservation],
    publication_equities: list[DailyEquityObservation],
    raw_sha256: str | None,
    source_status: str,
    parser_error: str | None = None,
) -> dict[str, Any]:
    trade_by_symbol: dict[str, str] = {}
    for row in trade_date_equities:
        if row.symbol in trade_by_symbol:
            raise AlphaContractError(
                f"{trade_session}: duplicate trade-date EQ symbol {row.symbol}"
            )
        trade_by_symbol[row.symbol] = row.isin

    publication_by_isin: dict[str, str] = {}
    for row in publication_equities:
        if row.isin in publication_by_isin:
            raise AlphaContractError(
                f"{publication_session}: duplicate publication-session EQ ISIN {row.isin}"
            )
        publication_by_isin[row.isin] = row.symbol

    normalized = []
    if rows is not None:
        for source_index, row in enumerate(rows):
            mapped_isin = trade_by_symbol.get(row.symbol)
            publication_symbol = (
                publication_by_isin.get(mapped_isin)
                if mapped_isin is not None
                else None
            )
            normalized.append(
                {
                    "source_row_index": source_index,
                    "security_name": row.security_name,
                    "source_symbol": row.symbol,
                    "trade_date": row.trade_date,
                    "quantity": row.quantity,
                    "trade_date_mapped_isin": mapped_isin,
                    "publication_symbol": publication_symbol,
                    "trade_date_identity_status": (
                        "MAPPED_EQ"
                        if mapped_isin is not None
                        else "UNMATCHED_EQ"
                    ),
                    "publication_continuity_status": (
                        "SAME_ISIN_PRESENT"
                        if publication_symbol is not None
                        else "NO_SAME_ISIN_ON_PUBLICATION_SESSION"
                    ),
                }
            )

    symbols = Counter(row["source_symbol"] for row in normalized)
    result: dict[str, Any] = {
        "publication_session": publication_session,
        "trade_session": trade_session,
        "source_status": source_status,
        "raw_sha256": raw_sha256,
        "source_row_count": len(normalized),
        "trade_date_mapped_row_count": sum(
            row["trade_date_identity_status"] == "MAPPED_EQ"
            for row in normalized
        ),
        "trade_date_unmatched_row_count": sum(
            row["trade_date_identity_status"] == "UNMATCHED_EQ"
            for row in normalized
        ),
        "publication_continuity_row_count": sum(
            row["publication_continuity_status"] == "SAME_ISIN_PRESENT"
            for row in normalized
        ),
        "publication_discontinuity_row_count": sum(
            row["publication_continuity_status"]
            == "NO_SAME_ISIN_ON_PUBLICATION_SESSION"
            for row in normalized
        ),
        "duplicate_symbol_row_count": sum(
            count - 1 for count in symbols.values() if count > 1
        ),
        "duplicate_symbols": sorted(
            symbol for symbol, count in symbols.items() if count > 1
        )[:25],
        "rows": normalized,
    }
    if parser_error is not None:
        result["parser_error"] = parser_error
    return result


def summarize_p3b(
    sessions: list[dict[str, Any]],
    *,
    schemas: list[tuple[str, ...]],
) -> dict[str, Any]:
    if not sessions:
        raise AlphaContractError("D010 P3B sessions cannot be empty")
    publication_dates = [
        str(row["publication_session"]) for row in sessions
    ]
    if (
        publication_dates != sorted(publication_dates)
        or len(publication_dates) != len(set(publication_dates))
    ):
        raise AlphaContractError(
            "D010 P3B publication sessions must be unique and chronological"
        )

    ready = [
        row for row in sessions
        if row["source_status"] == "READY"
    ]
    source_rows = sum(int(row["source_row_count"]) for row in ready)
    mapped_rows = sum(
        int(row["trade_date_mapped_row_count"]) for row in ready
    )
    continuity_rows = sum(
        int(row["publication_continuity_row_count"]) for row in ready
    )
    ready_fraction = len(ready) / len(sessions)
    mapping_fraction = mapped_rows / source_rows if source_rows else 0.0
    continuity_fraction = (
        continuity_rows / mapped_rows if mapped_rows else 0.0
    )
    schema_set = {tuple(schema) for schema in schemas}
    duplicate_rows = sum(
        int(row["duplicate_symbol_row_count"]) for row in ready
    )

    passes = (
        ready_fraction >= MIN_READY_SESSION_FRACTION
        and len(schema_set) == 1
        and mapping_fraction >= MIN_TRADE_DATE_MAPPING_FRACTION
        and continuity_fraction >= MIN_PUBLICATION_CONTINUITY_FRACTION
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_P3B_ID,
        "evidence_class": "SOURCE_COVERAGE_IDENTITY_NO_RETURN_OUTCOMES",
        "publication_window_start": publication_dates[0],
        "publication_window_end": publication_dates[-1],
        "publication_session_count": len(sessions),
        "ready_session_count": len(ready),
        "ready_session_fraction": ready_fraction,
        "schema_count": len(schema_set),
        "schemas": [list(value) for value in sorted(schema_set)],
        "source_row_count": source_rows,
        "trade_date_mapped_row_count": mapped_rows,
        "trade_date_identity_mapping_fraction": mapping_fraction,
        "publication_continuity_row_count": continuity_rows,
        "publication_session_isin_continuity_fraction": continuity_fraction,
        "duplicate_symbol_row_count": duplicate_rows,
        "status": (
            "PROMOTE_P4_FEATURE_SEMANTICS"
            if passes
            else "SHORT_SELLING_HISTORICAL_VIABILITY_FAILED"
        ),
        "historical_viability_pass": passes,
        "row_absence_numeric_zero": False,
        "duplicate_rows_automatically_aggregated": False,
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def build_p3b_panel(
    *,
    sessions: list[dict[str, Any]],
    report_sha256: str,
) -> dict[str, Any]:
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-D010-P3B-SHORT-PANEL-v1",
        "evidence_class": "SOURCE_COVERAGE_IDENTITY_NO_RETURN_OUTCOMES",
        "report_sha256": report_sha256,
        "session_count": len(sessions),
        "sessions": sessions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
