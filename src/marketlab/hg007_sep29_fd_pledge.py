"""Original NSE Sep29 INOXGREEN diluted share and pledged promoter evidence.

P010 recovered the exact post-QIP official Reg31 XBRL. This P011
reconciles precise original aggregate facts to a *dated reported*
fully-diluted share count and governance warning. No current/live
price, net debt, WWIL cash flows, return probabilities or trades.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from marketlab.hg007_qip_capitalization import (
    build_qip_denominator_audit,
    load_verified_source_references,
)

AUDIT_ID = "HG007-P011-INOXGREEN-SEP29-ORIGINAL-FD-AND-PLEDGE-v1"
ORIGINAL_XML_SHA = (
    "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
)
ORIGINAL_XML_PATH = Path(
    "research/hg007/inoxgreen-post-qip-reg31/raw/sha256/"
    + ORIGINAL_XML_SHA + ".xml"
)
REPORT_PATH = Path("research/hg007/inoxgreen-post-qip-reg31/original-source-receipt-v1.json")
REPORT_GIT_BLOB = "c9e4301edc61f2467fd557f308bf202705568474"
QIP_AUDIT_PATH = Path(
    "research/hg007/inoxgreen-sep2026-qip/post-qip-market-cap-audit-v1.json"
)
QIP_AUDIT_BLOB = "e31efd712fdfae378d7be8263883c521f1411d43"
TOTAL_CONTEXT = "ShareholdingPattern_ContextI"
PROMOTER_CONTEXT = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
MAIN_CONTEXT = "MainI"
SHARES_ISSUED = 419_602_518
SHARES_FD = 422_070_138
ESOP_OUTSTANDING = 2_467_620
PROMOTER_SHARES = 225_317_291
PROMOTER_PLEDGED_SHARES = 4_900_000
HISTORICAL_PRICES = {"2026-10-01": 159.0, "2026-10-09": 128.92}
INR_CRORE = 10_000_000


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _fact(root: ET.Element, concept: str, context: str, unit: str | None) -> str:
    matches = [
        element for element in root.iter()
        if _local(element.tag) == concept
        and element.attrib.get("contextRef") == context
    ]
    if len(matches) != 1:
        raise ValueError(f"ambiguous/missing exact NSE Reg31 fact {context}/{concept}")
    row = matches[0]
    if unit is not None and row.attrib.get("unitRef") != unit:
        raise ValueError(f"wrong original NSE fact unit for {context}/{concept}")
    value = (row.text or "").strip()
    if not value:
        raise ValueError(f"blank NSE original Reg31 source fact {concept}")
    return value


def _int(root: ET.Element, concept: str, context: str) -> int:
    value = _fact(root, concept, context, "shares")
    if not value.isdecimal():
        raise ValueError(f"NSE Reg31 {concept} should be integer shares")
    return int(value)


def _fraction(root: ET.Element, concept: str, context: str) -> float:
    value = float(_fact(root, concept, context, "pure"))
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"invalid official Reg31 fraction for {concept}")
    return value


def _boolean(root: ET.Element, concept: str) -> bool:
    value = _fact(root, concept, MAIN_CONTEXT, None).casefold()
    if value not in ("true", "false"):
        raise ValueError(f"invalid issuer Reg31 boolean for {concept}")
    return value == "true"


def load_verified_reg31(root: Path) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    raw_report = (root / REPORT_PATH).read_bytes()
    if _git_blob(raw_report) != REPORT_GIT_BLOB:
        raise ValueError("original post-QIP Reg31 source receipt changed")
    report = json.loads(raw_report)
    if not isinstance(report, dict):
        raise TypeError("original Reg31 source report must be object")
    if (
        report.get("report_id") != "HG007-P010-INOXGREEN-OFFICIAL-POST-QIP-SHAREHOLDING-v1"
        or report.get("symbol") != "INOXGREEN"
        or report.get("evidence_status") != "ORIGINAL_REPORTED_POST_QIP_SHARE_COUNTS_CAPTURED"
        or report.get("xbrl_original_raw_sha256") != ORIGINAL_XML_SHA
        or report.get("live_capital_allowed") is not False
    ):
        raise ValueError("official Reg31 source result scope changed")
    source = report.get("selected_original_filing")
    if (
        not isinstance(source, dict)
        or source.get("report_date") != "2026-09-29"
        or source.get("broadcast_at_utc") != "2026-10-08T13:24:47Z"
        or source.get("record_id") != "213525"
        or source.get("xbrl_url") != (
            "https://nsearchives.nseindia.com/corporate/xbrl/"
            "SHP_1734551_08102026065442_WEB.xml"
        )
    ):
        raise ValueError("date/revision of original NSE Reg31 source changed")
    raw = (root / ORIGINAL_XML_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_XML_SHA:
        raise ValueError("original Reg31 raw XML sha256 changed")
    if len(raw) != report.get("xbrl_original_byte_count"):
        raise ValueError("original XBRL raw byte count disagrees with NSE capture")

    qip_raw = (root / QIP_AUDIT_PATH).read_bytes()
    if _git_blob(qip_raw) != QIP_AUDIT_BLOB:
        raise ValueError("original QIP dated cap result changed")
    qip = json.loads(qip_raw)
    if (
        qip.get("audit_id") != "HG007-P008-INOXGREEN-QIP-DATED-CAPITALIZATION-v1"
        or qip.get("post_qip_fully_diluted_market_cap_authorized") is not False
    ):
        raise ValueError("prior dated basic cap scope changed")

    return raw, report, qip


def build_sep29_report(raw: bytes, captured: dict, old_qip: dict) -> dict:
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_XML_SHA:
        raise ValueError("original Reg31 XBRL SHA does not match source")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("cannot parse original NSE Reg31 issuer XML") from exc

    basic = _int(root, "NumberOfFullyPaidUpEquityShares", TOTAL_CONTEXT)
    fd = _int(
        root,
        "NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities",
        TOTAL_CONTEXT,
    )
    issued_options = _int(root, "NumberOfSharesOutstandingESOPGranted", TOTAL_CONTEXT)
    total_convertibles = _int(
        root, "NumberOfSharesUnderlyingOutstandingConvertibleSecuritiesWarrantsAndESOP",
        TOTAL_CONTEXT,
    )
    warrants = _boolean(root, "WhetherTheListedEntityHasIssuedAnyWarrants")
    convertible = _boolean(root, "WhetherTheListedEntityHasIssuedAnyConvertibleSecurities")
    esop_flag = _boolean(root, "WhetherTheListedEntityHasGrantedAnyESOPWhichAreOutstanding")
    promoter_shares = _int(root, "NumberOfFullyPaidUpEquityShares", PROMOTER_CONTEXT)
    promoter_frac = _fraction(
        root, "ShareholdingAsAPercentageOfTotalNumberOfShares", PROMOTER_CONTEXT
    )
    promoter_pledge = _int(root, "NumberOfSharesEncumberedUnderPledged", PROMOTER_CONTEXT)
    pledge_frac_promoter = _fraction(
        root, "EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares",
        PROMOTER_CONTEXT,
    )
    pledge_total = _int(root, "NumberOfSharesEncumberedUnderPledged", TOTAL_CONTEXT)
    pledge_frac_total = _fraction(
        root, "EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares",
        TOTAL_CONTEXT,
    )
    pledge_flag = _boolean(root, "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledged")
    other_encum = _boolean(
        root, "WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDU"
    )
    ndu_flag = _boolean(
        root, "WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertaking"
    )
    if (
        basic != SHARES_ISSUED
        or fd != SHARES_FD
        or issued_options != ESOP_OUTSTANDING
        or total_convertibles != issued_options
        or fd != basic + total_convertibles
        or warrants or convertible or not esop_flag
        or promoter_shares != PROMOTER_SHARES
        or promoter_pledge != PROMOTER_PLEDGED_SHARES
        or promoter_pledge != pledge_total
        or not pledge_flag or other_encum or ndu_flag
    ):
        raise ValueError("unreconciled source-reported capital or pledge identity")
    if any(
        abs(delta) > 0.00005 for delta in (
            promoter_frac - promoter_shares / basic,
            pledge_frac_promoter - promoter_pledge / promoter_shares,
            pledge_frac_total - pledge_total / basic,
        )
    ):
        raise ValueError("original published ownership and pledged-share ratios disagree")
    if captured.get("reported_share_counts") != {
        "fully_paid_shares": basic, "fully_diluted_shares": fd
    }:
        raise ValueError("NSE Reg31 P010 captured share counts disagree with raw XML")
    governance = captured.get("reported_promoter_and_pledge_context")
    if (
        not isinstance(governance, dict)
        or governance.get("parser_status") != "CORE_READY"
        or governance.get("promoter_encumbrance", {}).get("pledge") is not True
        or not math.isclose(governance.get("promoter_percentage"), promoter_frac * 100)
    ):
        raise ValueError("original governance parser cannot reconcile shareholding")
    old_caps = old_qip.get("post_qip_basic_share_capital_sensitivities")
    if not isinstance(old_caps, dict):
        raise TypeError("original dated basic-capitalization report missing")
    dated = {}
    for day, price in HISTORICAL_PRICES.items():
        old_entry = old_caps.get(day)
        if not isinstance(old_entry, dict):
            raise TypeError("original basic cap date absent")
        if old_entry.get("post_sep29_issued_basic_shares") != basic or (
            old_entry.get("raw_nse_close_inr") != price
        ):
            raise ValueError("official dated basic cap context drifted")
        dated[day] = {
            "raw_nse_close_inr": price,
            "sep29_reported_basic_market_cap_inr_crore": basic * price / INR_CRORE,
            "sep29_reported_fd_market_cap_inr_crore": fd * price / INR_CRORE,
            "basis": "SEP29_REPORTED_SHARE_COUNTS_TIMES_HISTORICAL_NSE_CLOSE",
            "share_count_freshness_at_price_session_proven": False,
            "economic_wwil_enterprise_value_verified": False,
        }

    return {
        "schema_version": 1,
        "review_id": AUDIT_ID,
        "classification": "NSE_SEP29_ORIGINAL_REPORTED_FD_AND_PLEDGE_NOT_CURRENT_STOCK_VALUE",
        "symbol": "INOXGREEN",
        "isin": "INE510W01014",
        "shareholding_report_date": "2026-09-29",
        "shareholding_first_broadcast_utc": "2026-10-08T13:24:47Z",
        "original_nse_raw_xbrl_sha256": ORIGINAL_XML_SHA,
        "reported_paid_issued_shares": basic,
        "reported_fully_diluted_shares_including_esop": fd,
        "reported_outstanding_esop_shares": issued_options,
        "no_other_convertibles_or_warrants_reported": not (warrants or convertible),
        "reported_promoter_shares": promoter_shares,
        "reported_promoter_ownership_pct": promoter_frac * 100,
        "reported_promoter_pledged_shares": promoter_pledge,
        "reported_promoter_pledge_pct_promoter_shares": pledge_frac_promoter * 100,
        "reported_promoter_pledge_pct_total_issued_shares": pledge_frac_total * 100,
        "original_cash_purchased_price_reference_dates": dated,
        "pledge_lender_collateral_terms_and_creation_date_verified": False,
        "post_sep29_additional_issuance_or_pledge_change_excluded": False,
        "oct12_current_fd_share_count_independently_verified": False,
        "cash_adjusted_enterprise_value_authorized": False,
        "wwil_target_ebitda_and_free_cashflow_verified": False,
        "company_probability_weighted_return_published": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
