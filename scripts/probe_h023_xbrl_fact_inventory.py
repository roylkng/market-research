from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from probe_h023_nse_shareholding import _request_with_retries, _session as _api_session
from probe_h023_nse_shareholding_xbrl import _fetch, _resolve_xbrl_url
from probe_h023_nse_shareholding_xbrl import _session as _xbrl_session

BROADCAST_FORMAT = "%d-%b-%Y %H:%M:%S"
INTERESTING_RE = re.compile(
    r"mutual|fund|sharehold|percent|category|shareholder|institution",
    re.IGNORECASE,
)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _latest_rows(payload: object, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TypeError("NSE shareholding master payload is not a list")
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        url = _resolve_xbrl_url(str(row.get("xbrl") or ""))
        broadcast = _clean(row.get("broadcastDate"))
        if url is None or not broadcast:
            continue
        try:
            timestamp = datetime.strptime(broadcast.upper(), BROADCAST_FORMAT)
        except ValueError:
            continue
        candidates.append((timestamp, {**row, "resolved_xbrl_url": url}))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in candidates[:limit]]


def _context_summary(root: ET.Element) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        tokens: list[str] = []
        attributes: list[dict[str, str]] = []
        for nested in element.iter():
            text = _clean(nested.text)
            if text:
                tokens.append(text)
            for key, value in nested.attrib.items():
                cleaned = _clean(value)
                if cleaned:
                    attributes.append(
                        {"element": _local_name(nested.tag), "attribute": key, "value": cleaned}
                    )
        contexts[context_id] = {
            "text_tokens": tokens[:100],
            "attributes": attributes[:100],
        }
    return contexts


def _inventory_xml(raw: bytes) -> dict[str, Any]:
    root = ET.fromstring(raw)
    contexts = _context_summary(root)
    facts: list[dict[str, Any]] = []
    mutual_contexts: set[str] = set()
    interesting_facts: list[dict[str, Any]] = []
    tag_counts: dict[str, int] = {}

    for element in root.iter():
        name = _local_name(element.tag)
        tag_counts[name] = tag_counts.get(name, 0) + 1
        context_ref = element.attrib.get("contextRef") or element.attrib.get("contextref")
        if not context_ref:
            continue
        value = _clean(element.text)
        fact = {
            "concept": name,
            "context_ref": context_ref,
            "value": value[:500],
            "unit_ref": element.attrib.get("unitRef") or element.attrib.get("unitref"),
            "decimals": element.attrib.get("decimals"),
        }
        facts.append(fact)
        if "mutual fund" in value.casefold():
            mutual_contexts.add(context_ref)
        if INTERESTING_RE.search(name) or INTERESTING_RE.search(value):
            interesting_facts.append(fact)

    for context_id, summary in contexts.items():
        searchable = json.dumps(summary, ensure_ascii=False).casefold()
        if "mutual fund" in searchable:
            mutual_contexts.add(context_id)

    mutual_context_facts = [fact for fact in facts if fact["context_ref"] in mutual_contexts]
    matching_tag_counts = {
        name: count
        for name, count in sorted(tag_counts.items())
        if INTERESTING_RE.search(name)
    }
    return {
        "root_tag": _local_name(root.tag),
        "context_count": len(contexts),
        "fact_count": len(facts),
        "mutual_fund_context_ids": sorted(mutual_contexts),
        "mutual_fund_contexts": {
            context_id: contexts.get(context_id) for context_id in sorted(mutual_contexts)
        },
        "mutual_fund_context_facts": mutual_context_facts[:300],
        "interesting_facts": interesting_facts[:300],
        "interesting_tag_counts": matching_tag_counts,
    }


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory official NSE shareholding XBRL facts")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--symbols", nargs="+", default=["RELIANCE", "INFY", "ABB"])
    parser.add_argument("--filings-per-symbol", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()

    api_session = _api_session(args.timeout_seconds)
    xbrl_session = _xbrl_session()
    reports: list[dict[str, Any]] = []
    for symbol_raw in args.symbols:
        symbol = symbol_raw.strip().upper()
        response = _request_with_retries(
            api_session,
            symbol=symbol,
            timeout=args.timeout_seconds,
            attempts=args.attempts,
        )
        selected = _latest_rows(response.json(), limit=args.filings_per_symbol)
        filings: list[dict[str, Any]] = []
        for row in selected:
            url = str(row["resolved_xbrl_url"])
            xbrl = _fetch(
                xbrl_session,
                url=url,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            filings.append(
                {
                    "broadcastDate": row.get("broadcastDate"),
                    "report_date": row.get("date"),
                    "recordId": row.get("recordId"),
                    "url": url,
                    "content_type": xbrl.headers.get("Content-Type"),
                    "content_length": len(xbrl.content),
                    "inventory": _inventory_xml(xbrl.content),
                }
            )
        reports.append({"symbol": symbol, "filings": filings})

    result = {
        "schema_version": 1,
        "hypothesis_probe": "H023-XBRL-XML-FACT-INVENTORY",
        "purpose": "Source-only inventory of current official NSE shareholding XBRL facts and contexts.",
        "symbol_reports": reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write(args.out, result)
    print(
        json.dumps(
            {
                row["symbol"]: [
                    {
                        "broadcastDate": filing["broadcastDate"],
                        "mutual_contexts": len(
                            filing["inventory"]["mutual_fund_context_ids"]
                        ),
                        "facts": filing["inventory"]["fact_count"],
                    }
                    for filing in row["filings"]
                ]
                for row in reports
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
