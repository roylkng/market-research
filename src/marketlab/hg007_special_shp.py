"""Verify NSE's 29-Sep-2026 *special allotment* Reg31 shareholding XBRL.

An allotment-date filing is deliberately not a standard 30-Sep quarter.
Official NSE master record 213525 was first broadcast 8 Oct 18:54 IST.
These as-of-date facts must not be backdated as public on 29 Sep.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.gf001_governance import parse_current_governance_xbrl
from marketlab.hg005_context import parse_shareholding_counts

AUDIT_ID = "HG007-P011-INOXGREEN-POST-QIP-SPECIAL-SHP-XBRL-v1"
MASTER_PATH = Path(
    "research/hg007/inoxgreen-reg31-source/source/"
    "master-dcdf2485a74174667ad230d5da200936d666a60137f62f06b52383b902d40e38.json"
)
MASTER_SHA256 = "dcdf2485a74174667ad230d5da200936d666a60137f62f06b52383b902d40e38"
SPECIAL_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "SHP_1734551_08102026065442_WEB.xml"
)
SPECIAL_ID = "213525"
REPORT_DATE = "2026-09-29"
BROADCAST_UTC = "2026-10-08T13:24:47Z"
BASIC_QIP_SHARES = 419_602_518
PRIOR_BASIC = 401_492_045
PRIOR_FD = 403_959_665
PRIOR_OPTIONS = PRIOR_FD-PRIOR_BASIC


def _utc(s: object) -> datetime:
    if not isinstance(s, str):
        raise TypeError("source acquisition timestamp must be ISO")
    v = datetime.fromisoformat(s)
    if v.tzinfo is None:
        raise ValueError("source time must include UTC offset")
    return v.astimezone(UTC)


def verify_original_special_master(root: Path) -> dict[str, Any]:
    raw = (root / MASTER_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != MASTER_SHA256:
        raise ValueError("original NSE 8 Oct shareholding master bytes changed")
    obj = json.loads(raw)
    if not isinstance(obj, list):
        raise TypeError("original NSE master should be an array")
    rows = [r for r in obj if isinstance(r, dict) and str(r.get("recordId")) == SPECIAL_ID]
    if len(rows) != 1:
        raise ValueError("no unique exchange post-QIP special record")
    row = rows[0]
    expected = {
        "date": "29-SEP-2026",
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "broadcastDate": "08-OCT-2026 18:54:47",
        "recordId": SPECIAL_ID,
        "xbrl": SPECIAL_URL,
        "pr_and_prgrp": "53.7",
        "public_val": "46.3",
    }
    for field, wanted in expected.items():
        if row.get(field) != wanted:
            raise ValueError(f"special original NSE master {field} changed")
    if row.get("submissionDate") != "08-OCT-2026":
        raise ValueError("special allotment source public submission date changed")
    if "Qualified Institutions Placement" not in str(row.get("remarksWeb")):
        raise ValueError("post-allotment original source meaning not verified")
    if not math.isclose(float(row["pr_and_prgrp"])+float(row["public_val"]),100):
        raise ValueError("promoter/public percentages do not reconcile to 100")
    return {
        "master_sha256": MASTER_SHA256,
        "master_url": (
            "https://www.nseindia.com/api/"
            "corporate-share-holdings-master?index=equities&symbol=INOXGREEN"
        ),
        "special_source_id": SPECIAL_ID,
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "as_of_allotment_date": REPORT_DATE,
        "exchange_first_public_broadcast_at_utc": BROADCAST_UTC,
        "original_xbrl_url": SPECIAL_URL,
        "issuer_master_promoter_percentage": 53.7,
        "issuer_master_public_percentage": 46.3,
        "special_not_standard_september_quarter": True,
    }


def interpret_special_xbrl(
    master: dict[str, Any], raw_xml: bytes, *, retrieved_at_utc: str
) -> dict[str, Any]:
    if (
        master.get("master_sha256") != MASTER_SHA256
        or master.get("special_source_id") != SPECIAL_ID
        or master.get("original_xbrl_url") != SPECIAL_URL
        or master.get("as_of_allotment_date") != REPORT_DATE
    ):
        raise ValueError("special NSE shareholding original master was substituted")
    retrieved = _utc(retrieved_at_utc)
    if retrieved < _utc(BROADCAST_UTC):
        raise ValueError("post-QIP special source cannot be seen before NSE broadcast")
    if not isinstance(raw_xml, bytes) or not 1000 <= len(raw_xml) <= 2_000_000:
        raise ValueError("original official shareholding XBRL bytes missing or too large")
    shares = parse_shareholding_counts(raw_xml, symbol="INOXGREEN")
    gov = parse_current_governance_xbrl(
        raw_xml, symbol="INOXGREEN", report_date=REPORT_DATE, source_url=SPECIAL_URL
    )
    basic = shares["fully_paid_shares"]
    fd = shares["fully_diluted_shares"]
    if basic != BASIC_QIP_SHARES or fd < basic:
        raise ValueError("source QIP basic shares disagree with original Sep29 allotment")
    governance_ready = gov["parser_status"] == "CORE_READY"
    promoter = gov["promoter_percentage"] if governance_ready else None
    if governance_ready and (
        not isinstance(promoter, float)
        or not math.isclose(promoter,53.7,abs_tol=0.03)
    ):
        raise ValueError("original special NSE promoter percentage differs from master")
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": (
            "AS_OF_SEP29_SPECIAL_ISSUER_XBRL_NOT_FULL_OCTOBER_CURRENT_VALUATION"
        ),
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "source_original_master_sha256": MASTER_SHA256,
        "source_nse_record_id": SPECIAL_ID,
        "source_original_xbrl_url": SPECIAL_URL,
        "source_original_xbrl_sha256": hashlib.sha256(raw_xml).hexdigest(),
        "source_original_xbrl_bytes": len(raw_xml),
        "issuer_capital_date": REPORT_DATE,
        "nse_public_broadcast_utc": BROADCAST_UTC,
        "source_xbrl_retrieved_at_utc": retrieved.isoformat().replace("+00:00","Z"),
        "reported_issued_basic_shares_as_of_sep29": basic,
        "reported_fully_diluted_shares_as_of_sep29": fd,
        "reported_dilutive_instruments_delta_to_basic": fd-basic,
        "original_june_dilutive_instruments_count": PRIOR_OPTIONS,
        "change_in_dilutive_shares_since_june": fd-basic-PRIOR_OPTIONS,
        "promoter_pct": promoter,
        "public_pct": gov["public_percentage"] if governance_ready else None,
        "source_governance_parser_status": gov["parser_status"],
        "promoter_pledge_boolean_as_of_report": (
            gov["promoter_encumbrance"]["pledge"] if governance_ready else None
        ),
        "promoter_pledged_share_quantity_source_verified": False,
        "claim_of_4_9m_pledged_shares_verified": False,
        "sept29_xbrl_first_public_2026_10_08": True,
        "sept29_filing_is_a_standard_sep30_quarter": False,
        "no_issuances_after_sep29_independently_confirmed": False,
        "current_asof_oct11_fully_diluted_shares_confirmed": False,
        "parent_and_subsidiary_minorities_adjusted": False,
        "stock_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
