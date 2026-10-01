from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_d010_p1 import short_archive_url
from marketlab.alpha_d010_sources import PROBE_DATES

D010_P3A_ID = "AE001-D010-P3A-v1"


def inspect_short_raw(
    raw: bytes,
    *,
    session_date: date,
) -> dict[str, Any]:
    if not raw:
        raise AlphaContractError("D010 P3A short-selling raw bytes are empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("D010 P3A short-selling source is not UTF-8") from exc

    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(str(value).strip() for value in row)]
    if not rows:
        raise AlphaContractError("D010 P3A short-selling CSV is empty")
    header = [str(value).strip() for value in rows[0]]
    data = rows[1:]
    width_counts = Counter(len(row) for row in data)

    def cell(row: list[str], index: int) -> str:
        return str(row[index]).strip() if index < len(row) else ""

    date_index = header.index("Trade Date") if "Trade Date" in header else None
    symbol_index = header.index("Symbol Name") if "Symbol Name" in header else None
    quantity_index = header.index("Quantity") if "Quantity" in header else None

    date_counts: Counter[str] = Counter()
    empty_symbol_count = 0
    empty_quantity_count = 0
    quantity_parse_failure_count = 0

    for row in data:
        if date_index is not None:
            date_counts.update([cell(row, date_index)])
        if symbol_index is not None and not cell(row, symbol_index):
            empty_symbol_count += 1
        if quantity_index is not None:
            raw_quantity = cell(row, quantity_index)
            if not raw_quantity:
                empty_quantity_count += 1
            else:
                try:
                    float(raw_quantity.replace(",", ""))
                except ValueError:
                    quantity_parse_failure_count += 1

    return {
        "session_date": session_date.isoformat(),
        "source_url": short_archive_url(session_date),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "byte_length": len(raw),
        "header": header,
        "header_width": len(header),
        "nonempty_data_row_count": len(data),
        "row_width_counts": {
            str(key): value for key, value in sorted(width_counts.items())
        },
        "row_width_mismatch_count": sum(
            count for width, count in width_counts.items() if width != len(header)
        ),
        "first_rows": data[:3],
        "last_rows": data[-3:],
        "trade_date_counts": dict(sorted(date_counts.items())),
        "empty_symbol_count": empty_symbol_count,
        "empty_quantity_count": empty_quantity_count,
        "quantity_parse_failure_count": quantity_parse_failure_count,
    }


def summarize_p3a(
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = {value.isoformat() for value in PROBE_DATES}
    dates = {str(row["session_date"]) for row in diagnostics}
    if dates != expected or len(diagnostics) != len(PROBE_DATES):
        raise AlphaContractError("D010 P3A diagnostics do not match frozen dates")
    report = {
        "schema_version": 1,
        "diagnostic_id": D010_P3A_ID,
        "evidence_class": "SOURCE_FORMAT_DIAGNOSTIC_NO_RETURN_OUTCOMES",
        "diagnostics": sorted(
            diagnostics,
            key=lambda row: str(row["session_date"]),
        ),
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
