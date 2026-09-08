#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ADMIN_EXCLUDE = {
    "Disclosure under SEBI Takeover Regulations",
    "Spurt in Volume",
    "Price movement",
    "Action(s) taken or orders passed",
    "Action(s) initiated or orders passed",
    "Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company",
    "News Verification",
    "Shareholders meeting",
    "Copy of Newspaper Publication",
    "Analysts/Institutional Investor Meet/Con. Call Updates",
    "Monitoring Agency Report",
    "Record Date",
    "Appointment",
    "Resignation",
    "Cessation",
    "Change in Management",
    "Trading Window",
    "Dividend",
}

ORDER_ALWAYS = {"Bagging/Receiving of orders/contracts", "Awarding of order(s)/contract(s)"}
CAPACITY_ALWAYS = {
    "Capacity addition",
    "Commencement of commercial production/operations",
    "Adoption of new line(s) of business",
}
MNA_ALWAYS = {
    "Acquisition",
    "Amalgamation/Merger",
    "Public Announcement-Open Offer",
    "Open Offer",
    "Demerger",
    "Scheme of Arrangement",
    "Sale or disposal",
    "Other Restructuring",
    "Arrangements for strategic, technical, manufacturing, or marketing tie up",
}
REG_ALWAYS = {
    "Granting/withdrawal/surrender/cancellation/suspension of key licenses/ regulatory approvals"
}
GENERIC = {
    "General Updates", "Updates", "Press Release", "Press Release (Revised)",
    "Agreements", "Memorandum of Understanding/Agreements", "Outcome of Board Meeting",
}

ORDER_AFFIRM = (
    "received", "secured", "awarded", "wins", "won", "bagged", "letter of award",
    "purchase order", "work order", "contract awarded", "selected as l1", "preferred bidder",
)
CAPACITY_TERMS = (
    "commissioning", "commercial production", "commercial operation", "capacity expansion",
    "capacity addition", "greenfield", "brownfield", "new facility", "new plant", "new line",
)
MNA_TERMS = (
    "acquire", "acquisition", "merger", "demerger", "disposal", "business transfer",
    "strategic investment", "change in control", "joint venture", "stake", "undertaking",
)
REG_TERMS = ("regulatory approval", "approved by", "approval from", "licence", "license", "certification", "authorisation", "authorization")
REG_COMMERCIAL = ("product", "facility", "plant", "market", "commercial", "drug", "device", "manufacturing", "service", "operation")
GUIDANCE_TERMS = ("guidance", "product launch", "commercial launch", "customer ramp", "product ramp", "network expansion", "first commercial", "new business")
SECURITIES_DESCRIPTIONS = {"Allotment of Securities", "Issue of Securities", "Qualified Institutional Placement", "Rights Issue", "Preferential issue"}


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def has_quantitative_token(text: str) -> bool:
    low = text.casefold()
    if re.search(r"\d", text):
        return True
    return any(token in low for token in ("%", "crore", "lakh", "million", "billion", "mw", "gw", "mtpa", "tonne", "stores", "sites", "customers"))


def retained_families(row: dict[str, Any]) -> list[str]:
    desc = str(row.get("description") or "").strip()
    summary = str(row.get("attachment_summary") or "").strip()
    low = summary.casefold()
    original = set(row.get("candidate_families") or [])
    if desc in ADMIN_EXCLUDE:
        return []
    retained: list[str] = []

    if "ORDER_CONTRACT" in original:
        keep = desc in ORDER_ALWAYS
        if not keep and desc in GENERIC:
            keep = any(term in low for term in ORDER_AFFIRM) and ("order" in low or "contract" in low)
        if keep:
            retained.append("ORDER_CONTRACT")

    if "CAPACITY_COMMISSIONING" in original:
        keep = desc in CAPACITY_ALWAYS
        if not keep and desc in GENERIC:
            keep = any(term in low for term in CAPACITY_TERMS)
        if keep:
            retained.append("CAPACITY_COMMISSIONING")

    if "MNA_CONTROL" in original:
        keep = desc in MNA_ALWAYS
        if not keep and desc in GENERIC:
            keep = any(term in low for term in MNA_TERMS)
        if keep:
            retained.append("MNA_CONTROL")

    if "REGULATORY_MARKET_OPENING" in original:
        keep = desc in REG_ALWAYS
        if desc in SECURITIES_DESCRIPTIONS:
            keep = False
        if not keep and desc in GENERIC:
            keep = any(term in low for term in REG_TERMS) and any(term in low for term in REG_COMMERCIAL)
        if keep:
            retained.append("REGULATORY_MARKET_OPENING")

    if "GUIDANCE_RAMP" in original:
        keep = desc == "Product launch" or desc in {"General Updates", "Updates", "Press Release", "Press Release (Revised)"}
        keep = keep and any(term in low for term in GUIDANCE_TERMS) and has_quantitative_token(summary)
        if keep:
            retained.append("GUIDANCE_RAMP")

    return retained


def main() -> None:
    ns = args()
    rows = json.loads(Path(ns.input).read_text())
    kept = []
    reason_counts = Counter()
    for row in rows:
        families = retained_families(row)
        if not families:
            reason_counts["FILTERED"] += 1
            continue
        copy = dict(row)
        copy["retained_families"] = families
        kept.append(copy)
        for family in families:
            reason_counts[family] += 1
    blind = [
        {
            "candidate_id": row["candidate_id"],
            "exchange_timestamp": row["exchange_timestamp"],
            "description": row["description"],
            "attachment_summary": row["attachment_summary"],
            "retained_families": row["retained_families"],
            "attachment_url": row["attachment_url"],
        }
        for row in kept
    ]
    out = Path(ns.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "status": "RETURN_BLIND_SOURCE_FILTER_COMPLETE_NOT_GRADED",
        "input_candidate_count": len(rows),
        "retained_candidate_count": len(kept),
        "filtered_candidate_count": len(rows) - len(kept),
        "retained_family_counts": {k: v for k, v in sorted(reason_counts.items()) if k != "FILTERED"},
        "future_returns_used": False,
        "symbols_used_for_filter": False,
    }
    (out / "filtered-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (out / "filtered-candidates.json").write_text(json.dumps(kept, indent=2, sort_keys=True) + "\n")
    (out / "filtered-blind-review-queue.json").write_text(json.dumps(blind, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
