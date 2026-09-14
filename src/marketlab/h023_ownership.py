from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

MF_CONTEXT_REF = "MutualFundsOrUTI_ContextI"
MF_SHAREHOLDING_CONCEPT = "ShareholdingAsAPercentageOfTotalNumberOfShares"
BROADCAST_FORMAT = "%d-%b-%Y %H:%M:%S"
REPORT_DATE_FORMAT = "%d-%b-%Y"
STANDARD_QUARTER_ENDS = frozenset({(3, 31), (6, 30), (9, 30), (12, 31)})
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


def _parse_report_date(value: object) -> date:
    text = _text(value)
    if not text:
        raise H023OwnershipError("NSE shareholding report date is missing")
    try:
        return datetime.strptime(text.upper(), REPORT_DATE_FORMAT).replace(tzinfo=IST).date()
    except ValueError as exc:
        raise H023OwnershipError(f"invalid NSE shareholding report date: {text}") from exc


def _parse_as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H023OwnershipError(f"invalid as-of timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise H023OwnershipError("as-of timestamp must include timezone")
    return parsed.astimezone(UTC)


def _approved_xbrl_url(value: object) -> str:
    text = _text(value)
    if not text.startswith("https://nsearchives.nseindia.com/") and not text.startswith(
        "https://archives.nseindia.com/"
    ):
        raise H023OwnershipError("NSE XBRL URL is missing or not on an approved archive host")
    if not text.casefold().endswith((".xml", ".html", ".xhtml")):
        raise H023OwnershipError("NSE shareholding XBRL URL has unsupported suffix")
    return text


def is_standard_quarter_end(report_date: str) -> bool:
    try:
        parsed = date.fromisoformat(report_date)
    except ValueError:
        return False
    return (parsed.month, parsed.day) in STANDARD_QUARTER_ENDS


def previous_quarter_end(report_date: str) -> str:
    try:
        parsed = date.fromisoformat(report_date)
    except ValueError as exc:
        raise H023OwnershipError(f"invalid canonical report date: {report_date}") from exc
    key = (parsed.month, parsed.day)
    if key == (3, 31):
        return date(parsed.year - 1, 12, 31).isoformat()
    if key == (6, 30):
        return date(parsed.year, 3, 31).isoformat()
    if key == (9, 30):
        return date(parsed.year, 6, 30).isoformat()
    if key == (12, 31):
        return date(parsed.year, 9, 30).isoformat()
    raise H023OwnershipError(f"report date is not a standard quarter end: {report_date}")


def _eligible_filings(
    payload: object,
    *,
    symbol: str,
    as_of_utc: str | None = None,
) -> tuple[tuple[datetime, OwnershipFiling], ...]:
    if not isinstance(payload, list):
        raise H023OwnershipError("NSE shareholding master payload must be a list")
    wanted = symbol.strip().upper()
    if not wanted:
        raise H023OwnershipError("symbol is empty")
    as_of = _parse_as_of(as_of_utc)
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
        if as_of is not None and broadcast.astimezone(UTC) > as_of:
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
                    report_date=report_date.isoformat(),
                    broadcast_at_utc=broadcast.astimezone(UTC).isoformat().replace(
                        "+00:00", "Z"
                    ),
                    xbrl_url=xbrl_url,
                ),
            )
        )
    return tuple(candidates)


def select_latest_revision_for_report_date(
    payload: object,
    *,
    symbol: str,
    report_date: str,
    as_of_utc: str | None = None,
) -> OwnershipFiling | None:
    if not is_standard_quarter_end(report_date):
        raise H023OwnershipError(f"report date is not a standard quarter end: {report_date}")
    matches = [
        item
        for item in _eligible_filings(payload, symbol=symbol, as_of_utc=as_of_utc)
        if item[1].report_date == report_date
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1].record_id), reverse=True)
    return matches[0][1]


def select_latest_adjacent_quarter_filings(
    payload: object,
    *,
    symbol: str,
    as_of_utc: str | None = None,
) -> tuple[OwnershipFiling, ...]:
    eligible = _eligible_filings(payload, symbol=symbol, as_of_utc=as_of_utc)
    quarter_dates = sorted(
        {
            filing.report_date
            for _broadcast, filing in eligible
            if is_standard_quarter_end(filing.report_date)
        },
        reverse=True,
    )
    if not quarter_dates:
        return ()
    current_date = quarter_dates[0]
    prior_date = previous_quarter_end(current_date)
    current = select_latest_revision_for_report_date(
        payload,
        symbol=symbol,
        report_date=current_date,
        as_of_utc=as_of_utc,
    )
    prior = select_latest_revision_for_report_date(
        payload,
        symbol=symbol,
        report_date=prior_date,
        as_of_utc=as_of_utc,
    )
    if current is None:
        return ()
    if prior is None:
        return (current,)
    return (current, prior)


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
        "availability_timestamp": "NSE broadcastDate interpreted as Asia/Kolkata",
        "eligible_report_dates": "standard calendar quarter ends only",
        "prior_period": "immediately previous calendar quarter end",
        "revision_selection": "latest public broadcast for each selected report date as of evaluation",
    }
