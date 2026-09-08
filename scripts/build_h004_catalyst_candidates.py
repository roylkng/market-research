#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from marketlab.nse import NSEClient

FAMILIES = {
    "ORDER_CONTRACT": (
        "order", "contract", "letter of award", "loa", "work order", "purchase order",
        "l1 bidder", "preferred bidder", "tender award", "bagging/receiving",
    ),
    "CAPACITY_COMMISSIONING": (
        "capacity expansion", "commissioning", "commercial production", "commercial operation",
        "new plant", "new facility", "new line", "greenfield", "brownfield", "capacity addition",
    ),
    "REGULATORY_MARKET_OPENING": (
        "regulatory approval", "product approval", "licence", "license", "certification",
        "authorisation", "authorization", "approval from", "approved by",
    ),
    "MNA_CONTROL": (
        "acquisition", "strategic investment", "merger", "demerger", "change in control",
        "business transfer", "slump sale", "acquire", "acquiring",
    ),
    "GUIDANCE_RAMP": (
        "guidance", "customer ramp", "product ramp", "network expansion", "first commercial",
        "commercial launch", "new business", "new product", "customer win",
    ),
}

ROUTINE_DESCRIPTIONS = (
    "shareholders meeting", "closure of trading window", "newspaper publication",
    "analysts/institutional investor meet", "monitoring agency report", "voting results",
    "scrutinizer", "dividend", "appointment", "resignation", "record date", "agm",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2025-10-01")
    p.add_argument("--end", default="2026-07-31")
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def chunks(start: date, end: date, days: int = 7):
    cur = start
    while cur <= end:
        last = min(end, cur + timedelta(days=days - 1))
        yield cur, last
        cur = last + timedelta(days=1)


def text(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "") for key in ("desc", "attchmntText", "sm_name", "symbol")
    ).strip()


def family_hits(value: str) -> list[str]:
    low = value.casefold()
    hits = []
    for family, terms in FAMILIES.items():
        if any(term in low for term in terms):
            hits.append(family)
    return hits


def routine_only(row: dict[str, Any], hits: list[str]) -> bool:
    if not hits:
        return True
    desc = str(row.get("desc") or "").casefold()
    summary = str(row.get("attchmntText") or "").casefold()
    if any(token in desc for token in ROUTINE_DESCRIPTIONS):
        # Keep only when the summary independently includes a strong catalyst phrase.
        summary_hits = family_hits(summary)
        return not summary_hits
    return False


def canonical_id(row: dict[str, Any]) -> str:
    payload = {
        "seq_id": str(row.get("seq_id") or ""),
        "symbol": str(row.get("symbol") or "").strip().upper(),
        "timestamp": str(row.get("exchdisstime") or row.get("an_dt") or ""),
        "attachment": str(row.get("attchmntFile") or ""),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def parse_timestamp(row: dict[str, Any]) -> datetime | None:
    value = str(row.get("exchdisstime") or row.get("an_dt") or "").strip()
    if not value:
        return None
    for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def semantic_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    # Deliberately excludes symbol/company identity and all market data. Date is retained only
    # as a source-ordering timestamp and does not expose future reaction.
    return {
        "candidate_id": candidate["candidate_id"],
        "exchange_timestamp": candidate["exchange_timestamp"],
        "description": candidate["description"],
        "attachment_summary": candidate["attachment_summary"],
        "candidate_families": candidate["candidate_families"],
        "attachment_url": candidate["attachment_url"],
    }


def normalize_summary(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main() -> None:
    ns = parse_args()
    start = date.fromisoformat(ns.start)
    end = date.fromisoformat(ns.end)
    out_dir = Path(ns.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = NSEClient(timeout=25, attempts=4)
    rows: list[dict[str, Any]] = []
    source_counts = []
    for a, b in chunks(start, end):
        payload, _ = client._json_get_with_raw(
            client.CORPORATE_ANNOUNCEMENT_ENDPOINT,
            params={
                "index": "equities",
                "from_date": a.strftime("%d-%m-%Y"),
                "to_date": b.strftime("%d-%m-%Y"),
            },
        )
        chunk_rows = payload if isinstance(payload, list) else []
        rows.extend(row for row in chunk_rows if isinstance(row, dict))
        source_counts.append({"start": a.isoformat(), "end": b.isoformat(), "rows": len(chunk_rows)})
        print(a, b, len(chunk_rows))

    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        timestamp = parse_timestamp(row)
        symbol = str(row.get("symbol") or "").strip().upper()
        if timestamp is None or not symbol:
            continue
        combined = text(row)
        hits = family_hits(combined)
        if routine_only(row, hits):
            continue
        cid = canonical_id(row)
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        candidates.append(
            {
                "candidate_id": cid,
                "symbol": symbol,
                "company": str(row.get("sm_name") or "").strip(),
                "exchange_timestamp": timestamp.isoformat(sep=" "),
                "description": normalize_summary(str(row.get("desc") or "")),
                "attachment_summary": normalize_summary(str(row.get("attchmntText") or "")),
                "candidate_families": hits,
                "attachment_url": str(row.get("attchmntFile") or "").strip() or None,
                "seq_id": str(row.get("seq_id") or ""),
                "industry": str(row.get("smIndustry") or "").strip() or None,
            }
        )

    # Collapse obvious exact-text restatements for the same symbol, retaining earliest source.
    candidates.sort(key=lambda row: (row["exchange_timestamp"], row["candidate_id"]))
    deduped: list[dict[str, Any]] = []
    seen_equiv: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        equiv = (
            candidate["symbol"],
            candidate["description"].casefold(),
            candidate["attachment_summary"].casefold(),
        )
        if equiv in seen_equiv:
            continue
        seen_equiv.add(equiv)
        deduped.append(candidate)

    blind = [semantic_payload(candidate) for candidate in deduped]
    by_family: dict[str, int] = {key: 0 for key in FAMILIES}
    for candidate in deduped:
        for family in candidate["candidate_families"]:
            by_family[family] += 1

    manifest = {
        "schema_version": 1,
        "experiment": "H004-HR004-CATALYST-CANDIDATES",
        "status": "CANDIDATE_EXTRACTION_ONLY_NOT_GRADED",
        "live_capital_allowed": False,
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "source": "NSE corporate-announcement API",
        "raw_announcement_rows": len(rows),
        "candidate_count": len(deduped),
        "candidate_family_counts": by_family,
        "source_chunk_counts": source_counts,
        "semantic_payload_excludes": ["symbol", "company", "industry", "market_returns", "future_outcomes"],
    }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out_dir / "candidates.json").write_text(json.dumps(deduped, indent=2, sort_keys=True) + "\n")
    (out_dir / "blind-review-queue.json").write_text(json.dumps(blind, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
