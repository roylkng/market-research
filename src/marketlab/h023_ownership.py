from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

MF_CONTEXT_REF = "MutualFundsOrUTI_ContextI"
MF_SHAREHOLDING_CONCEPT = "ShareholdingAsAPercentageOfTotalNumberOfShares"
BROADCAST_FORMAT = "%d-%b-%Y %H:%M:%S"
REPORT_DATE_FORMAT = "%d-%b-%Y"
IST = ZoneInfo("Asia/Kolkata")


class H023OwnershipError(ValueError):
    """Raised when official NSE ownership evidence cannot be parsed without guessing."""


@dataclass(frozen=True)
class OwnershipFiling:
    symbol: str
    record_id: str
    report_date: str
    broadcast_at_utc: str
    xbrl_url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MutualFundOwnership:
    context_ref: str
    concept: str
    unit_ref: str
    fraction: float
    percentage: float

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _text(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _parse_broadcast(value: object) -> datetime:
    text = _text(value)
    if not text:
        raise H023OwnershipError("NSE broadcastDate is missing")
    try:
        return datetime.strptime(text.upper(), BROADCAST_FORMAT).replace(tzinfo=IST)
    except ValueError as exc:
        raise H023OwnershipError(f"invalid NSE broadcastDate: {text}") from exc


def _parse_report_date(value: object) -> str:
    text = _text(value)
    if not text:
        raise H023OwnershipError("NSE shareholding report date is missing")
    try:
        parsed = datetime.strptime(text.upper(), REPORT_DATE_FORMAT).replace(tzinfo=IST).date()
    except ValueError as exc:
        raise H023OwnershipError(f"invalid NSE shareholding report date: {text}") from exc
    return parsed.isoformat()


def _approved_xbrl_url(value: object) -> str:
    text = _text(value)
    if not text.startswith("https://nsearchives.nseindia.com/") and not text.startswith(
        "https://archives.nseindia.com/"
    ):
        raise H023OwnershipError("NSE XBRL URL is missing or not on an approved archive host")
    if not text.casefold().endswith((".xml", ".html", ".xhtml")):
        raise H023OwnershipError("NSE shareholding XBRL URL has unsupported suffix")
    return text


def select_latest_distinct_filings(
    payload: object,
    *,
    symbol: str,
    count: int = 2,
) -> tuple[OwnershipFiling, ...]:
    if not isinstance(payload, list):
        raise H023OwnershipError("NSE shareholding master payload must be a list")
    if count < 1:
        raise H023OwnershipError("filing count must be positive")
    wanted = symbol.strip().upper()
    if not wanted:
        raise H023OwnershipError("symbol is empty")

    candidates: list[tuple[datetime, OwnershipFiling]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        observed_symbol = _text(row.get("symbol")).upper()
        if observed_symbol and observed_symbol != wanted:
            continue
        try:
            broadcast = _parse_broadcast(row.get("broadcastDate"))
            report_date = _parse_report_date(row.get("date"))
            xbrl_url = _approved_xbrl_url(row.get("xbrl"))
        except H023OwnershipError:
            continue
        record_id = _text(row.get("recordId"))
        if not record_id:
            continue
        candidates.append(
            (
                broadcast,
                OwnershipFiling(
                    symbol=wanted,
                    record_id=record_id,
                    report_date=report_date,
                    broadcast_at_utc=broadcast.astimezone(UTC).isoformat().replace(
                        "+00:00", "Z"
                    ),
                    xbrl_url=xbrl_url,
                ),
            )
        )
    candidates.sort(key=lambda item: (item[0], item[1].record_id), reverse=True)

    selected: list[OwnershipFiling] = []
    seen_report_dates: set[str] = set()
    for _broadcast, filing in candidates:
        if filing.report_date in seen_report_dates:
            continue
        selected.append(filing)
        seen_report_dates.add(filing.report_date)
        if len(selected) == count:
            break
    return tuple(selected)


def parse_mutual_fund_ownership_xbrl(raw: bytes) -> MutualFundOwnership:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise H023OwnershipError(f"invalid NSE shareholding XML: {exc}") from exc

    context_ids = {
        element.attrib.get("id")
        for element in root.iter()
        if _local_name(element.tag).casefold() == "context" and element.attrib.get("id")
    }
    if MF_CONTEXT_REF not in context_ids:
        raise H023OwnershipError(f"missing exact Mutual Fund context: {MF_CONTEXT_REF}")

    matches: list[ET.Element] = []
    for element in root.iter():
        if _local_name(element.tag) != MF_SHAREHOLDING_CONCEPT:
            continue
        context_ref = element.attrib.get("contextRef") or element.attrib.get("contextref")
        if context_ref == MF_CONTEXT_REF:
            matches.append(element)
    if len(matches) != 1:
        raise H023OwnershipError(
            f"expected one Mutual Fund shareholding fact, found {len(matches)}"
        )

    fact = matches[0]
    unit_ref = fact.attrib.get("unitRef") or fact.attrib.get("unitref")
    if unit_ref != "pure":
        raise H023OwnershipError(f"unexpected Mutual Fund shareholding unit: {unit_ref}")
    raw_value = _text(fact.text)
    try:
        fraction = float(raw_value)
    except ValueError as exc:
        raise H023OwnershipError(f"non-numeric Mutual Fund ownership fact: {raw_value}") from exc
    if not math.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        raise H023OwnershipError(f"Mutual Fund ownership fraction out of range: {fraction}")
    return MutualFundOwnership(
        context_ref=MF_CONTEXT_REF,
        concept=MF_SHAREHOLDING_CONCEPT,
        unit_ref="pure",
        fraction=fraction,
        percentage=fraction * 100.0,
    )


def ownership_delta_pp(current: MutualFundOwnership, prior: MutualFundOwnership) -> float:
    result = current.percentage - prior.percentage
    if not math.isfinite(result):
        raise H023OwnershipError("Mutual Fund ownership delta is non-finite")
    return result


def parser_contract() -> dict[str, Any]:
    return {
        "context_ref": MF_CONTEXT_REF,
        "concept": MF_SHAREHOLDING_CONCEPT,
        "unit_ref": "pure",
        "value_semantics": "fraction_of_total_shares",
        "percentage_conversion": "fraction * 100",
        "signal_primitive": "current_percentage - prior_distinct_report_percentage",
        "filing_order": "NSE broadcastDate descending, latest revision per distinct report date",
        "availability_timestamp": "NSE broadcastDate interpreted as Asia/Kolkata",
    }
