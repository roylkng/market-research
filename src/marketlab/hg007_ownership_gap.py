"""Immutable Oct 10 NSE master no-data diagnostic for INOXGREEN.

A source returning {"data":[],"msg":"no data found"} proves only
the endpoint response at that capture time. It does NOT prove that
no original September filing existed on other official venues, and
does not confirm or disprove a third-party pledge quantity.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

EVIDENCE_ID = "HG007-P012-INOXGREEN-NSE-SHAREHOLDING-NO-DATA-v1"
RAW_PATH = Path(
    "research/hg007/inoxgreen-post-qip-ownership/"
    "2026-10-10-original-nse-master-empty.json"
)
RAW_SHA256 = "d08611f20f7e28174a42e3f68099de1aecd58417493ef33f17041aa179d4cf44"
RAW_CAPTURED_UTC = "2026-10-10T13:28:32.704556Z"
WORKFLOW_RUN = 38055817025
EXPECTED_ORIGINAL_ENVELOPE = {"data": [], "msg": "no data found"}
QIP_PATH = Path(
    "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json"
)
QIP_GIT_BLOB = "e31efd712fdfae378d7be8263883c521f1411d43"
JUNE_PROMOTER_SHARES = 225_317_291
JUNE_ISSUED_BASIC = 401_492_045
SEP_QIP_BASIC = 419_602_518
JUNE_OUTSTANDING_ESOPS = 2_467_620

OFFICIAL_JUNE_FILING = "https://www.inoxgreen.com/PDF/SHP_30JUNE2026R.html"
SECONDARY_SEPTEMBER = (
    "https://trendlyne.com/equity/share-holding/1127763/INOXGREEN/latest/"
    "inox-green-energy-services-ltd/"
)


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def build_original_empty_api_evidence(root: Path) -> dict[str, Any]:
    raw = (root / RAW_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != RAW_SHA256 or len(raw) != 33:
        raise ValueError("original NSE official master response raw bytes drifted")
    try:
        response = json.loads(raw)
    except ValueError as exc:
        raise ValueError("original NSE response is no longer valid JSON") from exc
    if response != EXPECTED_ORIGINAL_ENVELOPE or not isinstance(response["data"], list):
        raise ValueError("official NSE original endpoint response changed")
    original_qip = (root / QIP_PATH).read_bytes()
    if _git_blob(original_qip) != QIP_GIT_BLOB:
        raise ValueError("source-verified post-QIP share count upstream drifted")
    qip = json.loads(original_qip)
    if (
        qip.get("audit_id") != "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
        or qip.get("original_september_2026_nse_qip", {}).get(
            "post_qip_issued_basic_shares"
        ) != SEP_QIP_BASIC
        or qip.get("live_capital_allowed") is not False
    ):
        raise ValueError("original Sep QIP issuer-issued count or capital rule modified")
    original_issued = JUNE_ISSUED_BASIC
    basic_qip_delta = SEP_QIP_BASIC - original_issued
    if basic_qip_delta != 18_110_473 or JUNE_PROMOTER_SHARES >= original_issued:
        raise ValueError("issuer QIP/dilution source arithmetic no longer reconciles")
    old_pct = 100.0 * JUNE_PROMOTER_SHARES / JUNE_ISSUED_BASIC
    new_pct = 100.0 * JUNE_PROMOTER_SHARES / SEP_QIP_BASIC
    if not (
        math.isclose(old_pct, 56.12, abs_tol=0.005)
        and math.isclose(new_pct, 53.70, abs_tol=0.005)
    ):
        raise ValueError("unchanged promoter share-count dilution does not reconcile")

    return {
        "schema_version": 1,
        "evidence_id": EVIDENCE_ID,
        "classification": "OFFICIAL_EXACT_ENDPOINT_NO_DATA_NOT_NO_FILING_EXISTS",
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "source": {
            "source_url": (
                "https://www.nseindia.com/api/corporate-share-holdings-master"
                "?index=equities&symbol=INOXGREEN"
            ),
            "original_raw_path": str(RAW_PATH),
            "original_raw_sha256": RAW_SHA256,
            "original_raw_byte_count": len(raw),
            "http_status": 200,
            "source_captured_at_utc": RAW_CAPTURED_UTC,
            "github_workflow_run_id": WORKFLOW_RUN,
            "original_object_top_level_keys": ["data", "msg"],
            "original_data_array_length": 0,
            "original_message": response["msg"],
        },
        "original_june_2026_issuer_filing_url": OFFICIAL_JUNE_FILING,
        "original_june_2026_snapshot": {
            "report_date": "2026-06-30",
            "issued_basic_shares": JUNE_ISSUED_BASIC,
            "outstanding_esop_shares": JUNE_OUTSTANDING_ESOPS,
            "promoter_shares": JUNE_PROMOTER_SHARES,
            "promoter_pledge_disclosed": False,
            "promoter_percent_original_rounded": round(old_pct, 2),
        },
        "september_2026_qip_original_verified": {
            "original_reconciled_qip_audit_git_blob": QIP_GIT_BLOB,
            "allotment_date": "2026-09-29",
            "issued_basic_shares_after_allotment": SEP_QIP_BASIC,
            "additional_qip_shares": basic_qip_delta,
            "unchanged_promoter_shares_mechanical_post_qip_percent": new_pct,
            "september_original_reg31_shares_and_pledge_verified": False,
        },
        "unverified_secondary_pledge_claim": {
            "source": SECONDARY_SEPTEMBER,
            "stated_as_of_date": "2026-09-29",
            "reported_pledged_shares_not_officially_source_verified": 4_900_000,
            "current_promoter_pledge_status": "UNKNOWN_PENDING_ORIGINAL_FILING",
            "treat_as_governance_risk_pending_review_not_confirmed": True,
        },
        "interpretation": (
            "The original NSE master endpoint returned a successful HTTP 200 "
            "empty data array at this exact source-capture time. "
            "This does not establish that no September Regulation 31 filing "
            "exists through BSE, issuer website or a different official "
            "source channel. A third-party pledged-share count is not "
            "equivalent to original issuer-signed XBRL."
        ),
        "current_official_september_ownership_filings_verified": False,
        "current_employee_option_issued_outstanding_reverified": False,
        "current_promoter_pledged_share_quantity_verified": False,
        "investment_governance_risk_score_calculated": False,
        "company_expected_returns_calculated": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
