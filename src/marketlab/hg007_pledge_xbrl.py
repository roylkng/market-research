"""Original issuer XBRL audit of INOXGREEN promoter shares pledged on 29 Sep.

Verifies exact context-qualified NSE facts, not just text matching:
promoter-group aggregate, issuer total, and the named promoter
Inox Wind Limited. Earlier June source declared no promoter pledge.
Does NOT infer pledge creation date or October-11 current capital.
"""

from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

AUDIT_ID = "HG007-P012-INOXGREEN-EXACT-SEPT29-PLEDGE-AND-FD-v1"
SOURCE_SHA = "6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822"
SOURCE_PATH = Path(
    "research/hg007/inoxgreen-post-qip-special/raw/"
    + SOURCE_SHA + ".xml"
)
SOURCE_RECEIPT_PATH = Path(
    "research/hg007/inoxgreen-post-qip-special/original-receipt-v1.json"
)
P010_JUNE_PATH = Path(
    "research/hg007/inoxgreen-reg31-source/attempts/38085969447-1.json"
)
P011_RECEIPT_GIT_BLOB = "8990da5ab2d56c07b2f05942210861fab2eb17ba"
P010_JUNE_GIT_BLOB = "61f01f8fd9ddc460f469362cd33d56de8c897ce7"
PLEDGE_CONCEPT = "NumberOfSharesEncumberedUnderPledged"
SHARE_CONCEPT = "NumberOfFullyPaidUpEquityShares"
FD_CONCEPT = "NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities"
PLEDGE_PCT_CONCEPT = "EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares"

AGGREGATE_PROMOTER = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
AGGREGATE_ISSUER = "ShareholdingPattern_ContextI"
NAMED_PROMOTER = "OthersIndianShareholders_Context15"
NAME_CONTEXT = "D_OthersIndianShareholders_Context15"
REPORT_DATE = "2026-09-29"
SOURCE_BROADCAST = "2026-10-08T13:24:47Z"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False
    ).hexdigest()


def _read_json_with_blob(root: Path, path: Path, expected: str) -> dict[str, Any]:
    raw = (root / path).read_bytes()
    if _git_blob(raw) != expected:
        raise ValueError("upstream June/September original source receipt changed")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("upstream original source receipt is not an object")
    return payload


def load_original_source(root: Path) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    raw = (root / SOURCE_PATH).read_bytes()
    if _sha(raw) != SOURCE_SHA:
        raise ValueError("September original NSE XBRL SHA mismatch")
    p011 = _read_json_with_blob(root, SOURCE_RECEIPT_PATH, P011_RECEIPT_GIT_BLOB)
    p010 = _read_json_with_blob(root, P010_JUNE_PATH, P010_JUNE_GIT_BLOB)
    parsed = p011.get("parsed_special_facts")
    june = p010.get("official_xbrl_review")
    if (
        p011.get("status") != "ORIGINAL_QIP_SPECIAL_XBRL_SHARE_COUNTS_PARSED"
        or p011.get("original_xbrl_sha256") != SOURCE_SHA
        or p011.get("live_capital_allowed") is not False
        or not isinstance(parsed, dict)
        or parsed.get("reported_issued_basic_shares_as_of_sep29") != 419_602_518
        or parsed.get("reported_fully_diluted_shares_as_of_sep29") != 422_070_138
        or parsed.get("promoter_pledge_boolean_as_of_report") is not True
        or parsed.get("nse_public_broadcast_utc") != SOURCE_BROADCAST
    ):
        raise ValueError("prior special-date NSE source findings do not match")
    if (
        not isinstance(june, dict)
        or june.get("report_date") != "2026-06-30"
        or june.get("promoter_pledge_declared_as_of_report") is not False
        or june.get("governance_parser_status") != "CORE_READY"
        or p010.get("live_capital_allowed") is not False
    ):
        raise ValueError("June baseline source must independently show no pledge")
    return raw, parsed, june


def _name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _facts(root: ET.Element, concept: str, context: str, unit: str | None) -> list[str]:
    matches = []
    for node in root.iter():
        if _name(node) == concept and node.attrib.get("contextRef") == context:
            if unit is not None and node.attrib.get("unitRef") != unit:
                raise ValueError(f"{concept}/{context}: official original XBRL unit invalid")
            matches.append((node.text or "").strip())
    return matches


def _one_int(root: ET.Element, concept: str, context: str) -> int:
    matched = _facts(root, concept, context, "shares")
    if len(matched) != 1:
        raise ValueError(f"{concept}/{context}: exactly one XBRL fact required")
    try:
        value = int(matched[0].replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"{concept}/{context}: malformed share count") from exc
    if value < 0:
        raise ValueError(f"{concept}/{context}: negative share count")
    return value


def _one_ratio(root: ET.Element, concept: str, context: str) -> float:
    matched = _facts(root, concept, context, "pure")
    if len(matched) != 1:
        raise ValueError(f"{concept}/{context}: exactly one XBRL ratio required")
    try:
        value = float(matched[0])
    except ValueError as exc:
        raise ValueError(f"{concept}/{context}: malformed XBRL ratio") from exc
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{concept}/{context}: invalid XBRL ratio")
    return value


def _verify_original_issuer_dates(root: ET.Element) -> None:
    for context in (AGGREGATE_PROMOTER, AGGREGATE_ISSUER, NAMED_PROMOTER):
        matches = [
            node for node in root.iter()
            if _name(node) == "context" and node.attrib.get("id") == context
        ]
        if len(matches) != 1:
            raise ValueError(f"{context}: original period context missing/duplicate")
        dates = [
            (node.text or "").strip()
            for node in matches[0].iter() if _name(node) == "instant"
        ]
        if dates != [REPORT_DATE]:
            raise ValueError(f"{context}: original as-of Sept29 instant changed")


def build_sept29_promoter_pledge_audit(
    raw_xml: bytes,
    source_sept: dict[str, Any],
    source_june: dict[str, Any],
) -> dict[str, Any]:
    if _sha(raw_xml) != SOURCE_SHA:
        raise ValueError("NSE original XBRL does not match pinned exact bytes")
    if (
        source_sept.get("source_original_xbrl_sha256") != SOURCE_SHA
        or source_sept.get("nse_public_broadcast_utc") != SOURCE_BROADCAST
        or source_june.get("promoter_pledge_declared_as_of_report") is not False
    ):
        raise ValueError("original September/June source identities changed")
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise ValueError("original NSE source XBRL is malformed") from exc
    _verify_original_issuer_dates(root)

    group_pledged = _one_int(root, PLEDGE_CONCEPT, AGGREGATE_PROMOTER)
    group_shares = _one_int(root, SHARE_CONCEPT, AGGREGATE_PROMOTER)
    issuer_pledged = _one_int(root, PLEDGE_CONCEPT, AGGREGATE_ISSUER)
    issuer_shares = _one_int(root, SHARE_CONCEPT, AGGREGATE_ISSUER)
    issuer_fd = _one_int(root, FD_CONCEPT, AGGREGATE_ISSUER)
    named_shares = _one_int(root, SHARE_CONCEPT, NAMED_PROMOTER)
    named_pledged = _one_int(root, PLEDGE_CONCEPT, NAMED_PROMOTER)
    issuer_ratio = _one_ratio(root, PLEDGE_PCT_CONCEPT, AGGREGATE_ISSUER)
    group_ratio = _one_ratio(root, PLEDGE_PCT_CONCEPT, AGGREGATE_PROMOTER)
    named_ratio = _one_ratio(root, PLEDGE_PCT_CONCEPT, NAMED_PROMOTER)
    shareholders = _facts(root, "NameOfTheShareholder", NAME_CONTEXT, None)
    if shareholders != ["Inox Wind Limited"]:
        raise ValueError("exact XBRL named promoter does not match Inox Wind Limited")
    if (
        group_pledged != 4_900_000
        or group_pledged != issuer_pledged
        or group_pledged != named_pledged
        or issuer_shares != 419_602_518
        or issuer_fd != 422_070_138
        or group_shares != 225_317_291
        or named_shares != 205_274_791
        or not (0 < named_pledged <= named_shares <= group_shares <= issuer_shares)
    ):
        raise ValueError("original exact issuer/promoter pledged/FD/holding totals mismatch")
    for actual, declared in (
        (group_pledged/group_shares, group_ratio),
        (issuer_pledged/issuer_shares, issuer_ratio),
        (named_pledged/named_shares, named_ratio),
    ):
        if abs(actual-declared) > 0.0001:
            raise ValueError("reported XBRL pledge percent inconsistent with shares")

    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "OFFICIAL_SEPT29_PROMOTER_PLEDGE_AND_FD_ASOF_NOT_OCT11_CURRENT",
        "symbol": "INOXGREEN",
        "original_xbrl_sha256": SOURCE_SHA,
        "nse_special_shareholding_record_id": "213525",
        "issuer_asof_date": REPORT_DATE,
        "original_filing_public_broadcast_utc": SOURCE_BROADCAST,
        "reference_june_original_pledge_boolean": False,
        "sept29_original_pledge_boolean": True,
        "source_pledging_named_promoter": "Inox Wind Limited",
        "named_promoter_held_shares": named_shares,
        "named_promoter_pledged_shares": named_pledged,
        "promoter_group_total_shares": group_shares,
        "promoter_group_total_pledged_shares": group_pledged,
        "listed_company_total_basic_shares": issuer_shares,
        "listed_company_total_fully_diluted_shares": issuer_fd,
        "dilutive_instruments_share_difference": issuer_fd-issuer_shares,
        "pledged_percent_of_promoter_group": 100*group_pledged/group_shares,
        "pledged_percent_of_all_issued": 100*issuer_pledged/issuer_shares,
        "pledged_percent_of_named_promoter_holding": 100*named_pledged/named_shares,
        "xbrl_reported_group_fraction": group_ratio,
        "xbrl_reported_issuer_fraction": issuer_ratio,
        "xbrl_reported_named_promoter_fraction": named_ratio,
        "governance_risk_marker": "NEW_AS_OF_SEPT29_PROMOTER_PLEDGE_VERSUS_JUNE_REPORT",
        "exact_date_pledge_created_verified": False,
        "pledge_security_and_recourse_terms_verified": False,
        "no_post_sep29_pledge_changes_verified": False,
        "no_post_sep29_issuance_or_esop_exercises_verified": False,
        "current_oct11_fd_capitalization_verified": False,
        "issuer_target_price_or_expected_return_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
