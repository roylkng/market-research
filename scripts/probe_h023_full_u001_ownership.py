from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from probe_h023_nse_shareholding import _request_with_retries
from probe_h023_nse_shareholding import _session as _api_session
from probe_h023_nse_shareholding_xbrl import _fetch, _inventory_xbrl_records
from probe_h023_nse_shareholding_xbrl import _session as _xbrl_session

from marketlab.h023_ownership import (
    H023OwnershipError,
    MF_SHAREHOLDING_CONCEPT,
    parse_mutual_fund_ownership_xbrl,
    parser_contract,
    select_latest_distinct_filings,
)
from marketlab.universe import load_universe_snapshot


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _availability_metadata(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    keys: Counter[str] = Counter()
    timestamp_like: list[dict[str, str]] = []
    for item in inventory:
        for parent in item.get("parent_scalar_fields", []):
            for key, value in parent.items():
                keys[str(key)] += 1
                text = str(value or "")
                key_lower = str(key).casefold()
                if any(
                    token in key_lower
                    for token in (
                        "date",
                        "time",
                        "broadcast",
                        "filing",
                        "submit",
                        "receipt",
                        "report",
                    )
                ) and (":" in text or "t" in text.casefold()):
                    timestamp_like.append({"key": str(key), "value": text[:200]})
    return {
        "scalar_key_counts": dict(keys.most_common()),
        "timestamp_like_candidates": timestamp_like[:50],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-U001 source-only feasibility probe for H023 ownership"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--filings-per-symbol", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.08)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = load_universe_snapshot(args.universe)
    if len(universe.members) != 100:
        raise ValueError("H023 full-U001 probe requires the frozen 100-name U001 panel")
    if args.filings_per_symbol < 1 or args.pause_seconds < 0:
        raise ValueError("invalid H023 full-U001 probe configuration")

    api_session = _api_session(args.timeout_seconds)
    xbrl_session = _xbrl_session()
    symbol_reports: list[dict[str, Any]] = []
    category_coverage: dict[str, Counter[str]] = defaultdict(Counter)
    percentage_concept_counts: dict[str, Counter[str]] = defaultdict(Counter)
    all_inventory: list[dict[str, Any]] = []

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        report: dict[str, Any] = {
            "symbol": symbol,
            "master_status": "FAILED",
            "xbrl_reference_count": 0,
            "probed_filing_count": 0,
            "successful_filing_count": 0,
            "parsed_filing_count": 0,
            "filings": [],
            "error": None,
        }
        try:
            response = _request_with_retries(
                api_session,
                symbol=symbol,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            payload = response.json()
            inventory = _inventory_xbrl_records(payload)
            all_inventory.extend(inventory)
            report["master_status"] = "COMPLETE"
            report["xbrl_reference_count"] = len(inventory)
            selected = select_latest_distinct_filings(
                payload,
                symbol=symbol,
                count=args.filings_per_symbol,
            )
            report["probed_filing_count"] = len(selected)
            for selected_filing in selected:
                filing: dict[str, Any] = {
                    "url": selected_filing.xbrl_url,
                    "record_id": selected_filing.record_id,
                    "report_date": selected_filing.report_date,
                    "broadcast_at_utc": selected_filing.broadcast_at_utc,
                    "status": "PENDING",
                    "terms": {"MUTUAL_FUNDS": False},
                    "percentage_concepts": {"MUTUAL_FUNDS": []},
                    "mutual_fund_ownership": None,
                    "error": None,
                }
                try:
                    xbrl_response = _fetch(
                        xbrl_session,
                        url=selected_filing.xbrl_url,
                        timeout=args.timeout_seconds,
                        attempts=args.attempts,
                    )
                    report["successful_filing_count"] += 1
                    try:
                        ownership = parse_mutual_fund_ownership_xbrl(xbrl_response.content)
                    except H023OwnershipError as exc:
                        filing["status"] = "PARSE_FAILED"
                        filing["error"] = f"{type(exc).__name__}: {exc}"
                    else:
                        filing["status"] = "COMPLETE"
                        filing["terms"]["MUTUAL_FUNDS"] = True
                        filing["percentage_concepts"]["MUTUAL_FUNDS"] = [
                            MF_SHAREHOLDING_CONCEPT
                        ]
                        filing["mutual_fund_ownership"] = ownership.to_dict()
                        report["parsed_filing_count"] += 1
                        category_coverage["MUTUAL_FUNDS"][symbol] += 1
                        percentage_concept_counts["MUTUAL_FUNDS"][
                            MF_SHAREHOLDING_CONCEPT
                        ] += 1
                except (RuntimeError, ValueError) as exc:
                    filing["status"] = "FETCH_FAILED"
                    filing["error"] = f"{type(exc).__name__}: {exc}"
                report["filings"].append(filing)
                if args.pause_seconds:
                    time.sleep(args.pause_seconds)
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
        symbol_reports.append(report)
        print(
            f"[{index:03d}/100] {symbol}: master={report['master_status']} "
            f"xbrl={report['xbrl_reference_count']} fetched="
            f"{report['successful_filing_count']}/{report['probed_filing_count']} parsed="
            f"{report['parsed_filing_count']}/{report['probed_filing_count']}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    summary = {
        "master_complete_symbols": sum(row["master_status"] == "COMPLETE" for row in symbol_reports),
        "symbols_with_any_xbrl": sum(row["xbrl_reference_count"] > 0 for row in symbol_reports),
        "symbols_with_two_or_more_xbrl": sum(row["xbrl_reference_count"] >= 2 for row in symbol_reports),
        "symbols_with_all_probed_filings_fetched": sum(
            row["probed_filing_count"] == args.filings_per_symbol
            and row["successful_filing_count"] == args.filings_per_symbol
            for row in symbol_reports
        ),
        "symbols_with_mutual_funds_in_every_probed_filing": sum(
            len(row["filings"]) == args.filings_per_symbol
            and all(filing.get("terms", {}).get("MUTUAL_FUNDS") for filing in row["filings"])
            for row in symbol_reports
        ),
        "symbols_with_mutual_fund_percentage_concept_in_every_probed_filing": sum(
            len(row["filings"]) == args.filings_per_symbol
            and all(
                filing.get("percentage_concepts", {}).get("MUTUAL_FUNDS")
                for filing in row["filings"]
            )
            for row in symbol_reports
        ),
    }
    report = {
        "schema_version": 2,
        "hypothesis_probe": "H023-OWNERSHIP-FULL-U001-SOURCE-PROBE",
        "purpose": (
            "Full frozen-U001 source-only feasibility audit of official NSE shareholding master "
            "records and exact XML Mutual Fund aggregate ownership facts. No price/return input "
            "is consumed."
        ),
        "universe_path": args.universe.as_posix(),
        "member_count": 100,
        "filings_per_symbol": args.filings_per_symbol,
        "parser_contract": parser_contract(),
        "summary": summary,
        "category_symbol_filing_counts": {
            term: dict(sorted(counter.items())) for term, counter in sorted(category_coverage.items())
        },
        "percentage_concept_counts": {
            term: dict(counter.most_common())
            for term, counter in sorted(percentage_concept_counts.items())
        },
        "availability_metadata": _availability_metadata(all_inventory),
        "symbol_reports": symbol_reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
