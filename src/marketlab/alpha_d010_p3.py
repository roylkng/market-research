from __future__ import annotations

import csv
import io
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import DailyEquityObservation

D010_P3_ID = "AE001-D010-P3-v1"
SHORT_SCHEMA = (
    "Security Name",
    "Symbol Name",
    "Trade Date",
    "Quantity",
)
SLB_SCHEMA = (
    "Sr no",
    "Security",
    "Series",
    "Outstanding Quantity at the end of the day",
)
MIN_READY_SESSION_FRACTION = 0.95
MIN_IDENTITY_MAPPING_FRACTION = 0.95


@dataclass(frozen=True)
class ShortSellingRow:
    security_name: str
    symbol: str
    trade_date: str
    quantity: float


@dataclass(frozen=True)
class SlbOpenPositionRow:
    symbol: str
    series: str
    outstanding_quantity: float


def _decode_csv(raw: bytes, *, source_name: str) -> csv.DictReader:
    if not raw:
        raise AlphaContractError(f"{source_name}: source bytes are empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError(
            f"{source_name}: source is not UTF-8 CSV"
        ) from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise AlphaContractError(f"{source_name}: missing CSV header")
    return reader


def _normalized_header(reader: csv.DictReader) -> tuple[str, ...]:
    assert reader.fieldnames is not None
    return tuple(str(value).strip() for value in reader.fieldnames)


def _finite_nonnegative(value: object, *, field: str) -> float:
    raw = str(value or "").strip().replace(",", "")
    try:
        parsed = float(raw)
    except ValueError as exc:
        raise AlphaContractError(f"{field}: invalid numeric value {value!r}") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise AlphaContractError(f"{field}: value must be finite and non-negative")
    return parsed


def _parse_source_date(value: object) -> date:
    raw = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise AlphaContractError(f"unsupported source date: {raw!r}")


def parse_short_selling(
    raw: bytes,
    *,
    session_date: date,
) -> tuple[list[ShortSellingRow], tuple[str, ...]]:
    reader = _decode_csv(raw, source_name="CM Short Selling")
    header = _normalized_header(reader)
    if header != SHORT_SCHEMA:
        raise AlphaContractError(
            f"CM Short Selling schema changed: {header!r}"
        )

    rows: list[ShortSellingRow] = []
    for index, raw_row in enumerate(reader, start=2):
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(row.values()):
            continue
        symbol = row["Symbol Name"].upper()
        if not symbol:
            raise AlphaContractError(
                f"CM Short Selling row {index}: empty Symbol Name"
            )
        trade_date = _parse_source_date(row["Trade Date"])
        if trade_date != session_date:
            raise AlphaContractError(
                f"CM Short Selling row {index}: trade date {trade_date} "
                f"does not equal session {session_date}"
            )
        rows.append(
            ShortSellingRow(
                security_name=row["Security Name"],
                symbol=symbol,
                trade_date=trade_date.isoformat(),
                quantity=_finite_nonnegative(
                    row["Quantity"],
                    field=f"CM Short Selling row {index} Quantity",
                ),
            )
        )
    return rows, header


def parse_slb_open_positions(
    raw: bytes,
) -> tuple[list[SlbOpenPositionRow], tuple[str, ...]]:
    reader = _decode_csv(raw, source_name="SLB Daily Open Positions")
    header = _normalized_header(reader)
    if header != SLB_SCHEMA:
        raise AlphaContractError(
            f"SLB Daily Open Positions schema changed: {header!r}"
        )

    rows: list[SlbOpenPositionRow] = []
    for index, raw_row in enumerate(reader, start=2):
        row = {
            str(key).strip(): str(value or "").strip()
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(row.values()):
            continue
        symbol = row["Security"].upper()
        if not symbol:
            raise AlphaContractError(
                f"SLB row {index}: empty Security"
            )
        rows.append(
            SlbOpenPositionRow(
                symbol=symbol,
                series=row["Series"].upper(),
                outstanding_quantity=_finite_nonnegative(
                    row["Outstanding Quantity at the end of the day"],
                    field=f"SLB row {index} Outstanding Quantity",
                ),
            )
        )
    return rows, header


def map_source_rows(
    *,
    short_rows: list[ShortSellingRow] | None,
    slb_rows: list[SlbOpenPositionRow] | None,
    equities: list[DailyEquityObservation],
    session_date: str,
    short_raw_sha256: str | None,
    slb_raw_sha256: str | None,
) -> dict[str, Any]:
    symbol_map: dict[str, str] = {}
    for row in equities:
        if row.symbol in symbol_map:
            raise AlphaContractError(
                f"{session_date}: duplicate UDiFF EQ symbol {row.symbol}"
            )
        symbol_map[row.symbol] = row.isin

    short_normalized = []
    if short_rows is not None:
        for source_index, row in enumerate(short_rows):
            isin = symbol_map.get(row.symbol)
            short_normalized.append(
                {
                    "source_row_index": source_index,
                    **asdict(row),
                    "mapped_isin": isin,
                    "identity_status": (
                        "MAPPED_EQ" if isin is not None else "UNMATCHED_EQ"
                    ),
                }
            )

    slb_normalized = []
    if slb_rows is not None:
        for source_index, row in enumerate(slb_rows):
            isin = symbol_map.get(row.symbol)
            slb_normalized.append(
                {
                    "source_row_index": source_index,
                    **asdict(row),
                    "mapped_isin": isin,
                    "identity_status": (
                        "MAPPED_EQ" if isin is not None else "UNMATCHED_EQ"
                    ),
                }
            )

    short_symbols = Counter(
        row["symbol"] for row in short_normalized
    )
    slb_symbols = Counter(
        row["symbol"] for row in slb_normalized
    )
    slb_symbol_series = Counter(
        (row["symbol"], row["series"]) for row in slb_normalized
    )

    return {
        "session_date": session_date,
        "udiff_eq_count": len(equities),
        "short_selling": {
            "source_status": (
                "READY" if short_rows is not None else "UNAVAILABLE"
            ),
            "raw_sha256": short_raw_sha256,
            "row_count": len(short_normalized),
            "mapped_row_count": sum(
                row["identity_status"] == "MAPPED_EQ"
                for row in short_normalized
            ),
            "unmatched_row_count": sum(
                row["identity_status"] == "UNMATCHED_EQ"
                for row in short_normalized
            ),
            "duplicate_symbol_row_count": sum(
                count - 1 for count in short_symbols.values() if count > 1
            ),
            "duplicate_symbols": sorted(
                symbol for symbol, count in short_symbols.items() if count > 1
            )[:25],
            "rows": short_normalized,
        },
        "slb_open_positions": {
            "source_status": (
                "READY" if slb_rows is not None else "UNAVAILABLE"
            ),
            "raw_sha256": slb_raw_sha256,
            "row_count": len(slb_normalized),
            "mapped_row_count": sum(
                row["identity_status"] == "MAPPED_EQ"
                for row in slb_normalized
            ),
            "unmatched_row_count": sum(
                row["identity_status"] == "UNMATCHED_EQ"
                for row in slb_normalized
            ),
            "duplicate_symbol_row_count": sum(
                count - 1 for count in slb_symbols.values() if count > 1
            ),
            "duplicate_symbol_series_row_count": sum(
                count - 1
                for count in slb_symbol_series.values()
                if count > 1
            ),
            "duplicate_symbols": sorted(
                symbol for symbol, count in slb_symbols.items() if count > 1
            )[:25],
            "series_counts": dict(
                sorted(
                    Counter(
                        row["series"] for row in slb_normalized
                    ).items()
                )
            ),
            "rows": slb_normalized,
        },
    }


def _family_summary(
    sessions: list[dict[str, Any]],
    *,
    key: str,
    schemas: list[tuple[str, ...]],
) -> dict[str, Any]:
    total_sessions = len(sessions)
    ready = [
        session[key]
        for session in sessions
        if session[key]["source_status"] == "READY"
    ]
    row_count = sum(int(row["row_count"]) for row in ready)
    mapped = sum(int(row["mapped_row_count"]) for row in ready)
    unmatched = sum(int(row["unmatched_row_count"]) for row in ready)
    ready_fraction = len(ready) / total_sessions if total_sessions else 0.0
    mapping_fraction = mapped / row_count if row_count else 0.0
    schema_set = {tuple(schema) for schema in schemas}
    duplicate_symbol_rows = sum(
        int(row["duplicate_symbol_row_count"]) for row in ready
    )

    passes = (
        ready_fraction >= MIN_READY_SESSION_FRACTION
        and len(schema_set) == 1
        and mapping_fraction >= MIN_IDENTITY_MAPPING_FRACTION
    )
    summary: dict[str, Any] = {
        "completed_market_session_count": total_sessions,
        "ready_session_count": len(ready),
        "ready_session_fraction": ready_fraction,
        "schema_count": len(schema_set),
        "schemas": [list(value) for value in sorted(schema_set)],
        "source_row_count": row_count,
        "mapped_row_count": mapped,
        "unmatched_row_count": unmatched,
        "identity_mapping_fraction": mapping_fraction,
        "duplicate_symbol_row_count": duplicate_symbol_rows,
        "historical_viability_pass": passes,
    }
    if key == "slb_open_positions":
        summary["duplicate_symbol_series_row_count"] = sum(
            int(row["duplicate_symbol_series_row_count"]) for row in ready
        )
        series_counter: Counter[str] = Counter()
        for row in ready:
            series_counter.update(row["series_counts"])
        summary["series_counts"] = dict(sorted(series_counter.items()))
    return summary


def summarize_p3(
    *,
    sessions: list[dict[str, Any]],
    short_schemas: list[tuple[str, ...]],
    slb_schemas: list[tuple[str, ...]],
) -> dict[str, Any]:
    if not sessions:
        raise AlphaContractError("D010 P3 sessions cannot be empty")
    dates = [str(row["session_date"]) for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError(
            "D010 P3 sessions must be unique and chronological"
        )

    short_summary = _family_summary(
        sessions,
        key="short_selling",
        schemas=short_schemas,
    )
    slb_summary = _family_summary(
        sessions,
        key="slb_open_positions",
        schemas=slb_schemas,
    )
    overall_pass = (
        short_summary["historical_viability_pass"]
        and slb_summary["historical_viability_pass"]
    )

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D010_P3_ID,
        "evidence_class": "SOURCE_COVERAGE_IDENTITY_NO_RETURN_OUTCOMES",
        "window_start": dates[0],
        "window_end": dates[-1],
        "completed_market_session_count": len(sessions),
        "short_selling": short_summary,
        "slb_open_positions": slb_summary,
        "row_absence_numeric_zero": False,
        "duplicate_rows_automatically_aggregated": False,
        "status": (
            "PROMOTE_P4_FEATURE_SEMANTICS"
            if overall_pass
            else "HISTORICAL_SOURCE_VIABILITY_FAILED"
        ),
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def build_p3_source_panel(
    *,
    sessions: list[dict[str, Any]],
    report_sha256: str,
) -> dict[str, Any]:
    panel = {
        "schema_version": 1,
        "panel_id": "AE001-D010-P3-SOURCE-PANEL-v1",
        "evidence_class": "SOURCE_COVERAGE_IDENTITY_NO_RETURN_OUTCOMES",
        "report_sha256": report_sha256,
        "session_count": len(sessions),
        "sessions": sessions,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
