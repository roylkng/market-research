"""OPEN003: audit evidence triage without manufacturing stock-selection alpha.

The 23-company register is an opportunity-investigation tracker, not a
screen of the NSE investable universe, owner-earnings estimator, or
recommendation. Selected consolidated CFO less selected PPE is only a
cash-flow **diagnostic** and never parent-attributable FCFE.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT = (
    Path(__file__).resolve().parents[1]
    / "research/broad-discovery/OPEN003_CROSS_UNIVERSE_EVIDENCE_20261025.json"
)
ORIGINAL = frozenset({
    "ANANTRAJ", "SAMBHV", "INOXGREEN", "DATAMATICS", "ACUTAAS",
    "ACE", "TRAVELFOOD", "POKARNA", "MAYURUNIQ", "PIXTRANS",
})
EXPANDED = frozenset({
    "BLS", "CRIZAC", "GESHIP", "TRANSRAILL", "CMSINFO", "EMMVEE",
    "GPPL", "ZUARIIND", "MASTEK", "INDIAMART", "AXTEL",
})
SECTOR_CHALLENGERS = frozenset({"SUNTV", "OIL"})
NUMERIC_YIELD_IDENTITIES = frozenset({"BLS", "MASTEK", "CRIZAC", "TRANSRAILL"})


def number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label}: expected number, never inferred")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label}: nonfinite value")
    return result


def evaluate(packet: dict) -> dict:
    if packet["schema"] != "OPEN003_20261025_BROAD_NSE_REVIEW_V1":
        raise ValueError("version mismatch")
    if packet["as_of"] != "2026-10-25" or packet["last_regular_market_session"] != "2026-10-23":
        raise ValueError("period or market price cutoff altered")
    if packet.get("research_only") is not True:
        raise ValueError("not research-only")
    claims = packet["claims"]
    if claims != {
        "complete_individual_NSE_underwriting": False,
        "original_hg009_selection_unchanged": True,
        "approved_positions": 0,
        "validated_alpha": False,
        "fully_underwritten_parent_fcfe_cases": 0,
    }:
        raise ValueError("illegal approval or prospective alpha mutation")

    rows = packet["candidates"]
    if len(rows) != 23 or len({r["symbol"] for r in rows}) != 23:
        raise ValueError("expected exactly 23 unique research candidates")
    groups = {}
    for group in ("ORIGINAL_10", "NEW_BROAD", "SECTOR_CHALLENGER"):
        groups[group] = {r["symbol"] for r in rows if r["group"] == group}
    if groups != {
        "ORIGINAL_10": ORIGINAL,
        "NEW_BROAD": EXPANDED,
        "SECTOR_CHALLENGER": SECTOR_CHALLENGERS,
    }:
        raise ValueError("company identities or research groups changed")
    if packet["sampling"] != {
        "original_ten": 10, "new_broad": 11, "sector_challengers": 2, "total": 23
    }:
        raise ValueError("sample denominator mismatch")

    reviewed = []
    for r in rows:
        symbol = r["symbol"]
        if r["investment_approved"] is not False:
            raise ValueError(f"{symbol} falsely approved")
        if (
            r["sustaining_parent_owner_cash_cr"] is not None
            or r["underwritten_intrinsic_value_per_share"] is not None
        ):
            raise ValueError(f"{symbol} has unverified owner cash or value")
        if not isinstance(r["primary_blocker"], str) or not r["primary_blocker"].strip():
            raise ValueError(f"{symbol} missing bear-thesis blocker")
        if not isinstance(r["next_gate"], str) or not r["next_gate"].strip():
            raise ValueError(f"{symbol} missing proof gate")
        link = urlsplit(r["source_url"])
        if link.scheme != "https" or not link.hostname:
            raise ValueError(f"{symbol} missing source reference")

        observed_price = r["price_inr"]
        if observed_price is None:
            if r["price_date"] is not None:
                raise ValueError(f"{symbol} has no dated quote")
        else:
            if r["price_date"] != "2026-10-23" or number(observed_price, "price") <= 0:
                raise ValueError(f"{symbol} price not observed at exact cutoff")
        cash = r["fy26_after_tax_consolidated_cfo_cr"]
        capex = r["fy26_selected_ppe_cash_cr"]
        mcap = r["reference_mcap_cr"]
        proxy = None
        proxy_yield = None
        if cash is not None:
            cash = number(cash, "consolidated after-tax CFO")
            if capex is not None:
                capex = number(capex, "selected PPE spend")
                if capex < 0:
                    raise ValueError(f"{symbol} capex sign anomaly")
                proxy = round(cash - capex, 4)
        if mcap is not None:
            if symbol not in NUMERIC_YIELD_IDENTITIES:
                # A value can be present for other economic contexts, but
                # cannot be promoted as a comparable owner-cash yield.
                pass
            mcap = number(mcap, "dated market capitalization")
            if mcap <= 0:
                raise ValueError("invalid equity value")
            if proxy is not None and symbol in NUMERIC_YIELD_IDENTITIES:
                proxy_yield = round(proxy / mcap * 100, 2)
        reviewed.append({
            "symbol": symbol,
            "group": r["group"],
            "review_stage": r["research_stage"],
            "consolidated_CFO_less_selected_PPE_cr": proxy,
            "naive_proxy_yield_pct": proxy_yield,
            "parent_owner_cash_verified": False,
            "investment_approved": False,
        })
    return {
        "schema": packet["schema"],
        "reviewed_candidates": len(rows),
        "group_counts": dict(sorted(Counter(x["group"] for x in rows).items())),
        "source_backed_parent_underwriting_complete": 0,
        "approved_positions": 0,
        "candidate_rows": reviewed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.input.read_text(encoding="utf-8"))),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
