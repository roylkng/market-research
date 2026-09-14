from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup
from probe_h023_nse_shareholding_xbrl import (
    _fetch,
    _inventory_xbrl_records,
    _session,
)

TERMS = {
    "MUTUAL_FUNDS": ("mutual fund",),
    "FPI": ("foreign portfolio investor", "fpi"),
    "INSURANCE": ("insurance compan",),
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _term_for_row(cells: list[str]) -> str | None:
    text = " | ".join(cells).casefold()
    matched = [name for name, needles in TERMS.items() if any(item in text for item in needles)]
    return matched[0] if len(matched) == 1 else None


def _concepts_in_row(tr: Any) -> list[dict[str, str | None]]:
    concepts: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None, str]] = set()
    for tag in tr.find_all(True):
        name = tag.attrs.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        concept = name.strip()
        context = tag.attrs.get("contextref") or tag.attrs.get("contextRef")
        context_text = str(context) if context is not None else None
        value = _clean(tag.get_text(" ", strip=True))
        key = (concept, context_text, value)
        if key in seen:
            continue
        seen.add(key)
        concepts.append(
            {
                "concept": concept,
                "context_ref": context_text,
                "value": value[:300],
            }
        )
    return concepts


def _rows(html: bytes) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    for index, tr in enumerate(soup.find_all("tr")):
        cells = [_clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["th", "td"])]
        if not cells:
            continue
        term = _term_for_row(cells)
        if term is None:
            continue
        results.append(
            {
                "row_index": index,
                "term": term,
                "cells": cells[:30],
                "concepts": _concepts_in_row(tr),
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit inline-XBRL concept stability for H023")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-filings-per-symbol", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = _session()
    reports: list[dict[str, Any]] = []
    concept_counts: dict[str, Counter[str]] = defaultdict(Counter)
    filing_counts: Counter[str] = Counter()

    for raw_path in sorted(args.raw_dir.glob("*.json")):
        symbol = raw_path.stem.upper()
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        inventory = _inventory_xbrl_records(payload)[: args.max_filings_per_symbol]
        filings: list[dict[str, Any]] = []
        for item in inventory:
            url = item["url"]
            try:
                response = _fetch(
                    session,
                    url=url,
                    timeout=args.timeout_seconds,
                    attempts=args.attempts,
                )
                parsed_rows = _rows(response.content)
                for term in TERMS:
                    term_rows = [row for row in parsed_rows if row["term"] == term]
                    if term_rows:
                        filing_counts[term] += 1
                    for row in term_rows:
                        for concept in row["concepts"]:
                            concept_counts[term][str(concept["concept"])] += 1
                filings.append(
                    {
                        "url": url,
                        "status_code": response.status_code,
                        "parent_scalar_fields": item["parent_scalar_fields"],
                        "ownership_rows": parsed_rows,
                    }
                )
            except (RuntimeError, requests.RequestException, ValueError) as exc:
                filings.append(
                    {
                        "url": url,
                        "status_code": None,
                        "parent_scalar_fields": item["parent_scalar_fields"],
                        "ownership_rows": [],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            if args.pause_seconds:
                time.sleep(args.pause_seconds)
        reports.append(
            {
                "symbol": symbol,
                "available_xbrl_count": len(_inventory_xbrl_records(payload)),
                "probed_filings": filings,
            }
        )

    report = {
        "schema_version": 1,
        "hypothesis_probe": "H023-OWNERSHIP-IXBRL-CONCEPT-PROBE",
        "purpose": "Source-only audit of official NSE inline-XBRL ownership concept stability.",
        "symbols": [row["symbol"] for row in reports],
        "concept_counts": {
            term: dict(counter.most_common()) for term, counter in sorted(concept_counts.items())
        },
        "filing_counts_with_term": dict(sorted(filing_counts.items())),
        "symbol_reports": reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(
        "H023 iXBRL concept probe: "
        + ", ".join(f"{term}={filing_counts[term]}" for term in sorted(TERMS)),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
