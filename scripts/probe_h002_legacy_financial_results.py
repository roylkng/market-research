from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.nse import NSEClient, NSEEndpoint

LEGACY_RESULTS_ENDPOINT = NSEEndpoint(
    "legacy_financial_results",
    "https://www.nseindia.com/api/corporates-financial-results",
)
DEFAULT_SYMBOLS = ("RELIANCE", "LT", "BEL", "INFY", "ITC")


class LegacyProbeError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    raise LegacyProbeError("legacy financial-results payload has no row list")


def _period_end(row: dict[str, Any]) -> str:
    for key in ("toDate", "to_date", "periodEnded", "period_ended"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _broadcast(row: dict[str, Any]) -> str:
    for key in ("broadCastDate", "broadcastDate", "broadcast_Date", "filingDate"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _basis(row: dict[str, Any]) -> str:
    for key in ("consolidated", "consolidatedOrStandalone", "cons"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _xbrl(row: dict[str, Any]) -> str:
    for key in ("xbrl", "xbrlFile", "xbrl_url"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _retain(root: Path, raw: bytes, *, symbol: str, role: str, suffix: str) -> dict[str, Any]:
    digest = _sha(raw)
    path = root / symbol / f"{role}-{digest}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {
        "sha256": digest,
        "path": str(path),
        "byte_count": len(raw),
    }


def _xml_shape(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    prefixes = []
    for token in ("in-bse-fin:", "in-capmkt:", "in-gaap:", "in-bse:"):
        if token in text:
            prefixes.append(token[:-1])
    local_concepts: list[str] = []
    for needle in (
        "BasicEarningsLossPerShare",
        "BasicEarnings",
        "NatureOfReportStandaloneConsolidated",
        "DateOfEndOfReportingPeriod",
        "RevenueFromOperations",
        "ProfitLossForPeriod",
    ):
        if needle in text:
            local_concepts.append(needle)
    return {
        "xml_prefix_markers": prefixes,
        "concept_markers": local_concepts,
        "starts_with_xml": text.lstrip("\ufeff\t\r\n ").startswith("<?xml"),
        "contains_xbrl_root": "xbrl" in text[:4096].casefold(),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    client = NSEClient(timeout=args.timeout, attempts=args.attempts)
    root = Path(args.store)
    symbols = tuple(
        item.strip().upper() for item in args.symbols.split(",") if item.strip()
    )
    if not symbols:
        symbols = DEFAULT_SYMBOLS
    output: list[dict[str, Any]] = []

    for symbol in symbols:
        payload, raw = client._json_get_with_raw(
            LEGACY_RESULTS_ENDPOINT,
            params={"index": "equities", "symbol": symbol, "period": "Quarterly"},
        )
        discovery = _retain(root, raw, symbol=symbol, role="discovery", suffix=".json")
        rows = _rows(payload)
        selected = [
            row
            for row in rows
            if _period_end(row) in {"30-Jun-2024", "30-Sep-2024", "31-Dec-2024"}
        ]
        if not selected:
            # Keep the metadata probe useful if NSE changes date spelling.
            selected = rows[:8]
        row_summaries = []
        xbrl_probes = []
        for row in selected:
            row_summaries.append(
                {
                    "period_end": _period_end(row),
                    "relating_to": row.get("relatingTo"),
                    "financial_year": row.get("financialYear"),
                    "period": row.get("period"),
                    "basis": _basis(row),
                    "broadcast": _broadcast(row),
                    "audited": row.get("audited"),
                    "ind_as": row.get("indAs"),
                    "xbrl": _xbrl(row),
                    "keys": sorted(str(key) for key in row),
                }
            )
        candidates = [row for row in selected if _xbrl(row)]
        # Probe at most one consolidated and one standalone source per symbol.
        chosen: list[dict[str, Any]] = []
        for wanted in ("consolidated", "standalone"):
            match = next(
                (
                    row
                    for row in candidates
                    if wanted in _basis(row).casefold()
                    and _period_end(row) in {"30-Jun-2024", "30-Sep-2024", "31-Dec-2024"}
                ),
                None,
            )
            if match is not None and match not in chosen:
                chosen.append(match)
        if not chosen and candidates:
            chosen.append(candidates[0])
        for index, row in enumerate(chosen):
            url = _xbrl(row)
            source_raw = client.archive_bytes(url)
            retained = _retain(
                root,
                source_raw,
                symbol=symbol,
                role=f"xbrl-{index}",
                suffix=".xml",
            )
            xbrl_probes.append(
                {
                    "period_end": _period_end(row),
                    "basis": _basis(row),
                    "broadcast": _broadcast(row),
                    "source_url": url,
                    "source": retained,
                    "shape": _xml_shape(source_raw),
                }
            )
        output.append(
            {
                "symbol": symbol,
                "discovery": discovery,
                "row_count": len(rows),
                "selected_rows": row_summaries,
                "xbrl_probes": xbrl_probes,
            }
        )
        print(symbol, len(rows), len(xbrl_probes), flush=True)

    report = {
        "schema_version": 1,
        "purpose": "H002 legacy NSE financial-results taxonomy probe",
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "endpoint": LEGACY_RESULTS_ENDPOINT.url,
        "symbols": list(symbols),
        "results": output,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe NSE pre-Integrated-Filing XBRL results")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--store", default=".marketlab-legacy-results-probe")
    parser.add_argument("--output", default="research/probes/h002-legacy-results-20260907/report.json")
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=5)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
