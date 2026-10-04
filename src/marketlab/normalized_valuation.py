from __future__ import annotations

import csv
import io
import math
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from marketlab.alpha import digest
from marketlab.events import sha256_bytes
from marketlab.marketdata import udiff_url

DIAGNOSTIC_ID = "NV001-D001-v1"
ANNUAL_PERIODS = (
    "2023-03-31",
    "2024-03-31",
    "2025-03-31",
    "2026-03-31",
)
CURRENT_SESSION = "2026-10-01"
UDIFF_START_DATE = date(2024, 7, 8)
IST = ZoneInfo("Asia/Kolkata")

EPS_CONCEPTS = (
    "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
    "BasicEarningsLossPerShareFromContinuingOperations",
)


class NV001SourceError(ValueError):
    """Raised when valuation source evidence cannot be resolved without guessing."""


@dataclass(frozen=True)
class AnnualFilingCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    source_family: str
    discovery_row_sha256: str


@dataclass(frozen=True)
class AnnualEPS:
    symbol: str
    isin: str | None
    accounting_basis: str
    period_end: str
    annual_start: str
    basic_eps: float
    raw_sha256: str
    source_url: str


@dataclass(frozen=True)
class PriceAnchor:
    symbol: str
    isin: str | None
    session_date: str
    close_price: float
    source_url: str
    raw_sha256: str
    source_family: str


@dataclass(frozen=True)
class _Context:
    context_id: str
    start_date: str | None
    end_date: str | None
    instant: str | None
    dimensional: bool


def _normalise(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_period(value: object) -> str | None:
    raw = _normalise(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_exchange_time(value: object) -> datetime:
    raw = _normalise(value)
    if not raw:
        raise NV001SourceError("filing publication timestamp is missing")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    except ValueError:
        pass
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(f"{raw} +0530", f"{fmt} %z").astimezone(UTC)
        except ValueError:
            continue
    raise NV001SourceError(f"unsupported filing publication timestamp: {value}")


def _legacy_basis(value: object) -> str | None:
    raw = " ".join(
        _normalise(value).casefold().replace("_", " ").replace("-", " ").split()
    )
    if raw == "consolidated":
        return "Consolidated"
    if raw in {"standalone", "non consolidated", "nonconsolidated"}:
        return "Standalone"
    return None


def _rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    return []


def _candidate(
    row: dict[str, Any],
    *,
    symbol: str,
    basis: str,
    period_end: str,
    source_family: str,
) -> AnnualFilingCandidate | None:
    row_symbol = _normalise(row.get("symbol") or row.get("SYMBOL")).upper()
    if row_symbol != symbol.upper():
        return None

    if source_family == "NSE_INTEGRATED_FILING":
        row_basis = _normalise(row.get("consolidated"))
        row_period = _parse_period(row.get("qe_Date"))
        url = _normalise(row.get("xbrl"))
        published_raw = (
            row.get("broadcast_Date")
            or row.get("revised_Date")
            or row.get("creation_Date")
        )
        row_type = _normalise(row.get("type")).casefold()
        if row_type and row_type != "integrated filing- financials":
            return None
    else:
        row_basis = _legacy_basis(row.get("consolidated"))
        row_period = _parse_period(
            row.get("toDate")
            or row.get("to_Date")
            or row.get("periodEnded")
            or row.get("period_end")
        )
        url = _normalise(row.get("xbrl"))
        published_raw = (
            row.get("broadCastDate")
            or row.get("broadcastDate")
            or row.get("broadcast_Date")
            or row.get("filingDate")
            or row.get("filing_Date")
        )

    if row_basis != basis or row_period != period_end:
        return None
    if not url or url in {"-", "--"}:
        return None
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower()
        not in {"nsearchives.nseindia.com", "archives.nseindia.com"}
    ):
        return None
    try:
        published = _parse_exchange_time(published_raw)
    except NV001SourceError:
        return None
    return AnnualFilingCandidate(
        symbol=symbol.upper(),
        accounting_basis=basis,
        period_end=period_end,
        exchange_published_at_utc=published.isoformat().replace("+00:00", "Z"),
        source_url=url,
        source_family=source_family,
        discovery_row_sha256=digest(row),
    )


def _select_earliest_unique(
    candidates: list[AnnualFilingCandidate],
) -> AnnualFilingCandidate:
    if not candidates:
        raise NV001SourceError("annual filing candidate unavailable")
    candidates = sorted(
        candidates,
        key=lambda row: (row.exchange_published_at_utc, row.source_url),
    )
    first_time = candidates[0].exchange_published_at_utc
    first = [row for row in candidates if row.exchange_published_at_utc == first_time]
    if len({row.source_url for row in first}) != 1:
        raise NV001SourceError("annual filing earliest timestamp is ambiguous")
    return first[0]


def select_four_year_annual_filings(
    integrated_payload: object,
    legacy_payload: object,
    *,
    symbol: str,
) -> tuple[str, tuple[AnnualFilingCandidate, ...]]:
    """Choose one accounting basis with exact FY23-FY26 annual filing coverage."""

    for basis in ("Consolidated", "Standalone"):
        selected: list[AnnualFilingCandidate] = []
        valid = True
        for period_end in ANNUAL_PERIODS:
            source_family = (
                "NSE_INTEGRATED_FILING"
                if period_end >= "2025-03-31"
                else "NSE_LEGACY_FINANCIAL_RESULTS"
            )
            payload = (
                integrated_payload
                if source_family == "NSE_INTEGRATED_FILING"
                else legacy_payload
            )
            candidates = [
                candidate
                for row in _rows(payload)
                if (
                    candidate := _candidate(
                        row,
                        symbol=symbol,
                        basis=basis,
                        period_end=period_end,
                        source_family=source_family,
                    )
                )
                is not None
            ]
            try:
                selected.append(_select_earliest_unique(candidates))
            except NV001SourceError:
                valid = False
                break
        if valid:
            return basis, tuple(selected)
    raise NV001SourceError("no single accounting basis has FY23-FY26 annual coverage")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _parse_contexts(root: ET.Element) -> dict[str, _Context]:
    contexts: dict[str, _Context] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        start_date = None
        end_date = None
        instant = None
        dimensional = False
        for child in element.iter():
            name = _local_name(child.tag)
            value = _parse_period(child.text)
            if name == "startDate":
                start_date = value
            elif name == "endDate":
                end_date = value
            elif name == "instant":
                instant = value
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        contexts[context_id] = _Context(
            context_id=context_id,
            start_date=start_date,
            end_date=end_date,
            instant=instant,
            dimensional=dimensional,
        )
    return contexts


def _facts(root: ET.Element) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = {}
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        value = _normalise(element.text)
        if not value:
            continue
        result.setdefault(_local_name(element.tag).casefold(), []).append(
            (context_ref, value)
        )
    return result


def _unique_text(
    facts: dict[str, list[tuple[str, str]]],
    concept: str,
) -> str | None:
    values = {value for _, value in facts.get(concept.casefold(), []) if value}
    if len(values) > 1:
        raise NV001SourceError(f"conflicting XBRL values for {concept}")
    return next(iter(values)) if values else None


def _parse_number(value: object) -> float | None:
    raw = _normalise(value).replace(",", "").replace("₹", "")
    if not raw or raw.casefold() in {"na", "n/a", "-", "--", "null"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return -parsed if negative else parsed


def parse_annual_basic_eps(
    raw: bytes,
    *,
    candidate: AnnualFilingCandidate,
) -> AnnualEPS:
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NV001SourceError("annual filing is not UTF-8") from exc
    stripped = document.lstrip("\ufeff\t\r\n ")
    if not (stripped.startswith("<?xml") or "<xbrli:xbrl" in stripped[:4096]):
        raise NV001SourceError("NV001 v1 requires XBRL annual filing bytes")
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise NV001SourceError(f"annual XBRL is not well formed: {exc}") from exc

    contexts = _parse_contexts(root)
    facts = _facts(root)
    symbol = _unique_text(facts, "Symbol")
    isin = _unique_text(facts, "ISIN")
    basis = _unique_text(facts, "NatureOfReportStandaloneConsolidated")
    if symbol is None or symbol.upper() != candidate.symbol.upper():
        raise NV001SourceError("annual filing symbol mismatch")
    if basis is None or basis.casefold() != candidate.accounting_basis.casefold():
        raise NV001SourceError("annual filing accounting basis mismatch")

    annual_contexts: set[str] = set()
    starts: set[str] = set()
    end = date.fromisoformat(candidate.period_end)
    for context_id, context in contexts.items():
        if context.dimensional or context.end_date != candidate.period_end:
            continue
        if context.start_date is None:
            continue
        start = date.fromisoformat(context.start_date)
        days = (end - start).days + 1
        if 350 <= days <= 380:
            annual_contexts.add(context_id)
            starts.add(context.start_date)
    if not annual_contexts or len(starts) != 1:
        raise NV001SourceError("annual EPS duration context is unavailable or ambiguous")
    annual_start = next(iter(starts))

    eps_value = None
    for concept in EPS_CONCEPTS:
        values = {
            _parse_number(value)
            for context_ref, value in facts.get(concept.casefold(), [])
            if context_ref in annual_contexts
        }
        values.discard(None)
        if len(values) > 1:
            raise NV001SourceError(f"conflicting annual EPS facts for {concept}")
        if values:
            eps_value = next(iter(values))
            break
    if eps_value is None:
        raise NV001SourceError("annual basic EPS is unavailable")
    if eps_value <= 0:
        raise NV001SourceError("annual basic EPS is nonpositive")

    return AnnualEPS(
        symbol=symbol.upper(),
        isin=isin,
        accounting_basis=candidate.accounting_basis,
        period_end=candidate.period_end,
        annual_start=annual_start,
        basic_eps=float(eps_value),
        raw_sha256=sha256_bytes(raw),
        source_url=candidate.source_url,
    )


def legacy_bhavcopy_url(session_date: date) -> str:
    mon = session_date.strftime("%b").upper()
    filename = f"cm{session_date.strftime('%d')}{mon}{session_date.year}bhav.csv.zip"
    return (
        "https://archives.nseindia.com/content/historical/EQUITIES/"
        f"{session_date.year}/{mon}/{filename}"
    )


def price_source(session_date: date) -> tuple[str, str]:
    if session_date >= UDIFF_START_DATE:
        return "NSE_UDIFF_BHAVCOPY", udiff_url(session_date)
    return "NSE_LEGACY_CM_BHAVCOPY", legacy_bhavcopy_url(session_date)


def _read_single_csv(raw_zip: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise NV001SourceError("bhavcopy ZIP must contain exactly one CSV")
            raw_csv = archive.read(names[0])
    except (zipfile.BadZipFile, KeyError) as exc:
        raise NV001SourceError(f"invalid bhavcopy ZIP: {exc}") from exc
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NV001SourceError("bhavcopy CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise NV001SourceError("bhavcopy CSV has no header")
    return list(reader.fieldnames), [dict(row) for row in reader]


def _positive(value: object, field: str) -> float:
    parsed = _parse_number(value)
    if parsed is None or parsed <= 0:
        raise NV001SourceError(f"{field} must be finite and positive")
    return parsed


def parse_price_close(
    raw_zip: bytes,
    *,
    source_family: str,
    session_date: date,
    symbol: str,
    expected_isin: str | None,
    source_url: str,
) -> PriceAnchor:
    fields, rows = _read_single_csv(raw_zip)
    wanted_symbol = symbol.upper()

    if source_family == "NSE_UDIFF_BHAVCOPY":
        required = {"TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb", "SctySrs", "ClsPric"}
        if not required.issubset(set(fields)):
            raise NV001SourceError("UDiFF header mismatch")
        candidates = [
            row
            for row in rows
            if (
                _normalise(row.get("TradDt")) == session_date.isoformat()
                and _normalise(row.get("Sgmt")).upper() == "CM"
                and _normalise(row.get("Src")).upper() == "NSE"
                and _normalise(row.get("FinInstrmTp")).upper() == "STK"
                and _normalise(row.get("SctySrs")).upper() == "EQ"
            )
        ]
        symbol_key = "TckrSymb"
        isin_key = "ISIN"
        close_key = "ClsPric"
    else:
        required = {"SYMBOL", "SERIES", "CLOSE", "ISIN"}
        if not required.issubset(set(fields)):
            raise NV001SourceError("legacy CM bhavcopy header mismatch")
        candidates = [
            row
            for row in rows
            if _normalise(row.get("SERIES")).upper() == "EQ"
        ]
        symbol_key = "SYMBOL"
        isin_key = "ISIN"
        close_key = "CLOSE"

    exact = [
        row
        for row in candidates
        if _normalise(row.get(symbol_key)).upper() == wanted_symbol
        and (
            expected_isin is None
            or _normalise(row.get(isin_key)).upper() == expected_isin.upper()
        )
    ]
    if len(exact) == 1:
        chosen = exact[0]
    elif expected_isin:
        by_isin = [
            row
            for row in candidates
            if _normalise(row.get(isin_key)).upper() == expected_isin.upper()
        ]
        if len(by_isin) != 1:
            raise NV001SourceError("bhavcopy identity unavailable")
        chosen = by_isin[0]
    else:
        raise NV001SourceError("bhavcopy symbol identity unavailable")

    observed_isin = _normalise(chosen.get(isin_key)).upper() or None
    return PriceAnchor(
        symbol=_normalise(chosen.get(symbol_key)).upper(),
        isin=observed_isin,
        session_date=session_date.isoformat(),
        close_price=_positive(chosen.get(close_key), "bhavcopy close"),
        source_url=source_url,
        raw_sha256=sha256_bytes(raw_zip),
        source_family=source_family,
    )


def publication_date_ist(candidate: AnnualFilingCandidate) -> date:
    published = datetime.fromisoformat(
        candidate.exchange_published_at_utc.replace("Z", "+00:00")
    )
    return published.astimezone(IST).date()


def candidate_price_dates(
    candidate: AnnualFilingCandidate,
    *,
    max_calendar_days: int = 10,
) -> tuple[date, ...]:
    start = publication_date_ist(candidate) + timedelta(days=1)
    return tuple(start + timedelta(days=offset) for offset in range(max_calendar_days))


def trailing_pe(close_price: float, basic_eps: float) -> float:
    if close_price <= 0 or basic_eps <= 0:
        raise NV001SourceError("trailing P/E requires positive price and EPS")
    value = close_price / basic_eps
    if not math.isfinite(value) or value <= 0:
        raise NV001SourceError("trailing P/E is invalid")
    return value


def record_sha(payload: dict[str, Any]) -> str:
    return digest(payload)
