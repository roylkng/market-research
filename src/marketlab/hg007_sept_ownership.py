"""Independent official 30-Sep-2026 INOXGREEN capital/pledge source probe.

The as-of snapshot comes strictly from the NSE shareholding master and
its exact source-linked XBRL. A missing, late, blocked, malformed or
nonmatching filing remains unverified. No third-party pledge numbers.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from marketlab.gf001_governance import parse_current_governance_xbrl
from marketlab.h023_acquisition import discover_standard_quarter_sources
from marketlab.hg005_context import parse_shareholding_counts

SYMBOL = "INOXGREEN"
REPORT_DATE = "2026-09-30"
QIP_ISSUED_SHARES = 419_602_518
PACK_ID = "HG007-P010-INOXGREEN-OFFICIAL-SEP2026-OWNERSHIP-v1"
NSE_MASTER_URL = (
    "https://www.nseindia.com/api/"
    "corporate-share-holdings-master?index=equities&symbol=INOXGREEN"
)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("source capture time must be an ISO timestamp")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid source timestamp") from exc
    if at.tzinfo is None:
        raise ValueError("source timestamp must include timezone")
    return at.astimezone(UTC)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _instant_for_primary_shareholding(raw: bytes) -> str:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("official NSE shareholding XML invalid") from exc
    matches = [
        ctx for ctx in root.iter()
        if ctx.tag.rsplit("}", 1)[-1].casefold() == "context"
        and ctx.get("id") == "ShareholdingPattern_ContextI"
    ]
    if len(matches) != 1:
        raise ValueError("exact aggregate shareholding XBRL context absent/duplicated")
    instants = [
        item.text.strip()
        for item in matches[0].iter()
        if item.tag.rsplit("}", 1)[-1].casefold() == "instant"
        and isinstance(item.text, str) and item.text.strip()
    ]
    if instants != [REPORT_DATE]:
        raise ValueError("official XBRL aggregate context instant does not match 30 Sep 2026")
    return instants[0]


def select_official_asof_master(
    master_bytes: bytes,
    *,
    captured_at_utc: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    captured = _timestamp(captured_at_utc)
    if not isinstance(master_bytes, bytes) or not master_bytes:
        raise ValueError("original NSE master JSON bytes missing")
    try:
        rows = json.loads(master_bytes)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("original NSE master is not parseable JSON") from exc
    sources = discover_standard_quarter_sources(rows, symbol=SYMBOL)
    sept = [
        source for source in sources
        if source["report_date"] == REPORT_DATE
        and _timestamp(source["broadcast_at_utc"]) <= captured
    ]
    summary = {
        "master_original_sha256": _sha(master_bytes),
        "master_original_byte_count": len(master_bytes),
        "source_count_all_standard_quarters_as_of_raw_response": len(sources),
        "sept_2026_sources_broadcast_by_capture_count": len(sept),
        "pending_later_broadcasts_are_not_backfilled": True,
    }
    if not sept:
        return None, summary
    latest = max(_timestamp(item["broadcast_at_utc"]) for item in sept)
    ties = [item for item in sept if _timestamp(item["broadcast_at_utc"]) == latest]
    if len(ties) != 1:
        raise ValueError("ambiguous latest official same-time Sep2026 revised filings")
    return ties[0], summary


def build_ownership_snapshot(
    *,
    master_raw: bytes | None,
    xbrl_raw: bytes | None,
    observed_at_utc: str,
    master_failure: str | None = None,
    xbrl_failure: str | None = None,
) -> dict[str, Any]:
    seen = _timestamp(observed_at_utc).isoformat().replace("+00:00", "Z")
    source = None
    description = None
    if master_raw is None:
        if not isinstance(master_failure, str) or not master_failure:
            raise ValueError("blocked master must preserve source-specific error")
        if xbrl_raw is not None:
            raise ValueError("XBRL cannot be detached from missing master")
        state = "OFFICIAL_MASTER_UNAVAILABLE"
        summary = None
    else:
        if master_failure is not None:
            raise ValueError("successful master source cannot have a failure")
        source, summary = select_official_asof_master(
            master_raw, captured_at_utc=seen
        )
        state = "SEPT_REPORT_NOT_OBSERVED_ON_OFFICIAL_MASTER_AT_CAPTURE"
        if source is None and xbrl_raw is not None:
            raise ValueError("XBRL cannot be supplied without source-listed Sep filing")
    share = None
    governance = None
    if source is not None:
        if xbrl_raw is None:
            if not isinstance(xbrl_failure, str) or not xbrl_failure:
                raise ValueError("missing official Sep XBRL must preserve fetch failure")
            state = "SEPT_REPORT_OFFICIAL_XBRL_UNAVAILABLE"
        else:
            if xbrl_failure is not None:
                raise ValueError("successful XBRL must not have a fetch error")
            try:
                _instant_for_primary_shareholding(xbrl_raw)
                share = parse_shareholding_counts(xbrl_raw, symbol=SYMBOL)
                governance = parse_current_governance_xbrl(
                    xbrl_raw,
                    symbol=SYMBOL,
                    report_date=REPORT_DATE,
                    source_url=source["xbrl_url"],
                )
            except (ValueError, TypeError) as exc:
                state = "OFFICIAL_XBRL_PARSE_OR_PERIOD_BLOCKED"
                description = f"{type(exc).__name__}: {exc}"
                share = None
                governance = None
            else:
                if share["fully_paid_shares"] != QIP_ISSUED_SHARES:
                    state = "SEPT_QUARTER_BASIC_SHARE_COUNT_DIFFERS_FROM_QIP"
                elif governance["parser_status"] != "CORE_READY":
                    state = "SHARES_VALID_GOVERNANCE_FACTS_NOT_CORE_READY"
                else:
                    state = "SEPT_OFFICIAL_XBRL_SHARE_COUNTS_AND_GOVERNANCE_CORE_READY"
    if xbrl_raw is None and xbrl_failure is not None and source is None:
        raise ValueError("XBRL failure requires selected official Sep source")

    pack = {
        "schema_version": 1,
        "snapshot_id": PACK_ID,
        "classification": "SOURCE_OBSERVED_SEP30_XBRL_NOT_POST_QIP_STOCK_ALPHA",
        "symbol": SYMBOL,
        "expected_isin_from_prior_issuer_evidence": "INE510W01014",
        "selected_report_date": REPORT_DATE,
        "observed_at_utc": seen,
        "original_official_master_url": NSE_MASTER_URL,
        "original_official_master_receipt": summary,
        "official_current_source": source,
        "original_official_xbrl_sha256": _sha(xbrl_raw) if xbrl_raw is not None else None,
        "original_official_xbrl_byte_count": (
            len(xbrl_raw) if xbrl_raw is not None else None
        ),
        "current_state": state,
        "source_error_or_block_reason": master_failure or xbrl_failure or description,
        "share_counts_as_of_report_date": share,
        "governance_as_of_report_date": governance,
        "promoter_pledged_share_count_verified": False,
        "secondary_vendor_reported_4900000_pledged_shares_adopted": False,
        "post_report_date_any_option_exercise_or_new_share_issue_verified": False,
        "as_of_2026_10_10_fully_diluted_shares_independently_proven": False,
        "independent_enterprise_value_and_cash_adjustment_verified": False,
        "stock_price_target_calculated": False,
        "company_completion_probability_published": False,
        "live_capital_allowed": False,
        "portfolio_eligibility_allowed": False,
    }
    if share is not None:
        pack["reported_sept_fully_diluted_minus_basic_securities"] = (
            share["fully_diluted_shares"] - share["fully_paid_shares"]
        )
        pack["sep_report_exact_xbrl_context_instant_checked"] = True
    else:
        pack["reported_sept_fully_diluted_minus_basic_securities"] = None
        pack["sep_report_exact_xbrl_context_instant_checked"] = False
    return pack


def validate_ownership_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("snapshot_id") != PACK_ID or snapshot.get("symbol") != SYMBOL:
        raise ValueError("not an original INOXGREEN Sep 2026 source observation")
    _timestamp(snapshot.get("observed_at_utc"))
    if snapshot.get("selected_report_date") != REPORT_DATE:
        raise ValueError("source report quarter changed")
    for flag in (
        "promoter_pledged_share_count_verified",
        "secondary_vendor_reported_4900000_pledged_shares_adopted",
        "post_report_date_any_option_exercise_or_new_share_issue_verified",
        "as_of_2026_10_10_fully_diluted_shares_independently_proven",
        "independent_enterprise_value_and_cash_adjustment_verified",
        "stock_price_target_calculated",
        "company_completion_probability_published",
        "live_capital_allowed",
        "portfolio_eligibility_allowed",
    ):
        if snapshot.get(flag) is not False:
            raise ValueError(f"Sep snapshot cannot promote {flag}")
