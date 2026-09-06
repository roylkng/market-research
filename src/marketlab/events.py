from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from marketlab.universe import UniverseSnapshot

PARSER_VERSION = "indas-table-v1"
XBRL_PARSER_VERSION = "indas-xbrl-2025-v1"
HISTORICAL_RECONSTRUCTION = "HISTORICAL_RECONSTRUCTION"
PROSPECTIVE = "PROSPECTIVE"


class EventParseError(ValueError):
    """Raised when a filing cannot be reconstructed without guessing."""


@dataclass(frozen=True)
class SourceProvenance:
    source_url: str
    captured_at_utc: str
    raw_sha256: str
    raw_path: str
    content_type: str
    source_mode: str
    exchange_published_at_utc: str | None = None
    discovery_sha256: str | None = None
    discovery_path: str | None = None
    cohort_id: str | None = None
    universe_rule_version: str | None = None
    universe_snapshot_sha256: str | None = None


@dataclass(frozen=True)
class FinancialEvent:
    schema_version: int
    parser_version: str
    mode: str
    economic_event_id: str
    version_id: str
    symbol: str
    isin: str | None
    company_name: str
    financial_year_start: str | None
    financial_year_end: str | None
    reporting_period_start: str | None
    reporting_period_end: str | None
    reporting_type: str | None
    reporting_quarter: str | None
    accounting_basis: str
    audited: bool | None
    board_approval_date: str | None
    prior_intimation_date: str | None
    currency: str | None
    rounding: str | None
    revenue_from_operations: float | None
    profit_before_exceptional_items_and_tax: float | None
    exceptional_items: float | None
    profit_before_tax: float | None
    net_profit_continuing_operations: float | None
    total_profit: float | None
    basic_eps: float | None
    diluted_eps: float | None
    operating_profit: float | None
    operating_margin: float | None
    unresolved_fields: tuple[str, ...]
    provenance: SourceProvenance

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _normalise_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = _normalise_text(value)
    if not text or text.casefold() in {"null", "na", "n/a", "-"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace("₹", "").strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _parse_audited(value: str | None) -> bool | None:
    if value is None:
        return None
    token = _normalise_text(value).casefold()
    if token == "audited":
        return True
    if token == "unaudited":
        return False
    return None


def _rows(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[list[str]] = []
    for row in soup.find_all("tr"):
        cells = [
            _normalise_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"])
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    return rows


def _find_value(rows: list[list[str]], label: str) -> str | None:
    wanted = _normalise_text(label).casefold()
    for cells in rows:
        lowered = [_normalise_text(cell).casefold() for cell in cells]
        for index, cell in enumerate(lowered):
            if cell == wanted:
                for candidate in cells[index + 1 :]:
                    if _normalise_text(candidate):
                        return candidate
    return None


def _find_number(rows: list[list[str]], label: str) -> float | None:
    return _parse_number(_find_value(rows, label))


def _required(rows: list[list[str]], label: str) -> str:
    value = _find_value(rows, label)
    if value is None:
        raise EventParseError(f"required filing field missing: {label}")
    return value


def _economic_event_id(symbol: str, period_end: str | None, basis: str, quarter: str | None) -> str:
    payload = f"{symbol}|{period_end or ''}|{basis}|{quarter or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _parse_utc_timestamp(value: str, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise EventParseError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise EventParseError(f"{field} must include timezone: {value}")
    return parsed.astimezone(UTC)


def _unresolved_fields() -> tuple[str, ...]:
    return (
        "operating_profit:not_a_standard_integrated_filing_line_item",
        "operating_margin:not_a_standard_integrated_filing_line_item",
    )


def _provenance(
    *,
    source_url: str,
    captured_at_utc: str,
    raw_sha256: str,
    raw_path: str,
    content_type: str,
    source_mode: str,
    exchange_published_at_utc: str | None,
    discovery_sha256: str | None,
    discovery_path: str | None,
    cohort_id: str | None,
    universe_rule_version: str | None,
    universe_snapshot_sha256: str | None,
) -> SourceProvenance:
    return SourceProvenance(
        source_url=source_url,
        captured_at_utc=captured_at_utc,
        raw_sha256=raw_sha256,
        raw_path=raw_path,
        content_type=content_type,
        source_mode=source_mode,
        exchange_published_at_utc=exchange_published_at_utc,
        discovery_sha256=discovery_sha256,
        discovery_path=discovery_path,
        cohort_id=cohort_id,
        universe_rule_version=universe_rule_version,
        universe_snapshot_sha256=universe_snapshot_sha256,
    )


def parse_indas_html(
    html: str,
    *,
    source_url: str,
    raw_sha256: str,
    raw_path: str,
    captured_at_utc: str,
    mode: str = HISTORICAL_RECONSTRUCTION,
    exchange_published_at_utc: str | None = None,
    discovery_sha256: str | None = None,
    discovery_path: str | None = None,
    cohort_id: str | None = None,
    universe_rule_version: str | None = None,
    universe_snapshot_sha256: str | None = None,
) -> FinancialEvent:
    """Parse standard fields from an NSE Integrated Filing Ind-AS HTML document."""

    rows = _rows(html)
    if not rows:
        raise EventParseError("filing contains no table rows")

    symbol = _required(rows, "NSE Symbol").upper()
    company_name = _required(rows, "Name of company")
    basis = _required(rows, "Nature of report standalone or consolidated")
    reporting_period_end = _find_value(rows, "Date of end of reporting period")
    quarter = _find_value(rows, "Reporting Quarter")
    event_id = _economic_event_id(symbol, reporting_period_end, basis, quarter)

    basic_eps = _find_number(
        rows, "Basic earnings (loss) per share from continuing and discontinued operations"
    )
    if basic_eps is None:
        basic_eps = _find_number(rows, "Basic earnings (loss) per share from continuing operations")
    diluted_eps = _find_number(
        rows, "Diluted earnings (loss) per share from continuing and discontinued operations"
    )
    if diluted_eps is None:
        diluted_eps = _find_number(
            rows, "Diluted earnings (loss) per share from continuing operations"
        )

    audited = _parse_audited(
        _find_value(rows, "Whether results are audited or unaudited for the quarter ended")
        or _find_value(rows, "Whether results are audited or unaudited")
    )

    provenance = _provenance(
        source_url=source_url,
        captured_at_utc=captured_at_utc,
        raw_sha256=raw_sha256,
        raw_path=raw_path,
        content_type="text/html",
        source_mode="NSE_INTEGRATED_FILING_IXBRL",
        exchange_published_at_utc=exchange_published_at_utc,
        discovery_sha256=discovery_sha256,
        discovery_path=discovery_path,
        cohort_id=cohort_id,
        universe_rule_version=universe_rule_version,
        universe_snapshot_sha256=universe_snapshot_sha256,
    )
    return FinancialEvent(
        schema_version=2 if mode == PROSPECTIVE else 1,
        parser_version=PARSER_VERSION,
        mode=mode,
        economic_event_id=event_id,
        version_id=f"{event_id}-{raw_sha256[:12]}",
        symbol=symbol,
        isin=_find_value(rows, "ISIN"),
        company_name=company_name,
        financial_year_start=_find_value(rows, "Date of start of financial year"),
        financial_year_end=_find_value(rows, "Date of end of financial year"),
        reporting_period_start=_find_value(rows, "Date of start of reporting period"),
        reporting_period_end=reporting_period_end,
        reporting_type=_find_value(rows, "Reporting Type"),
        reporting_quarter=quarter,
        accounting_basis=basis,
        audited=audited,
        board_approval_date=_find_value(rows, "Date of board meeting when results were approved"),
        prior_intimation_date=_find_value(
            rows,
            "Date on which prior intimation of the meeting for considering financial results "
            "was informed to the exchange",
        ),
        currency=_find_value(rows, "Description of presentation currency"),
        rounding=_find_value(rows, "Level of rounding used in financial results"),
        revenue_from_operations=_find_number(rows, "Revenue from operations"),
        profit_before_exceptional_items_and_tax=_find_number(
            rows, "Total profit before exceptional items and tax"
        ),
        exceptional_items=_find_number(rows, "Exceptional items"),
        profit_before_tax=_find_number(rows, "Total profit before tax"),
        net_profit_continuing_operations=_find_number(
            rows, "Net Profit Loss for the period from continuing operations"
        ),
        total_profit=_find_number(rows, "Total profit (loss) for period"),
        basic_eps=basic_eps,
        diluted_eps=diluted_eps,
        operating_profit=None,
        operating_margin=None,
        unresolved_fields=_unresolved_fields(),
        provenance=provenance,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _xbrl_facts(root: ET.Element) -> dict[str, list[tuple[str, str]]]:
    facts: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        text = _normalise_text(element.text or "")
        if text:
            facts[_local_name(element.tag)].append((context_ref, text))
    return dict(facts)


def _xbrl_primary_context(facts: dict[str, list[tuple[str, str]]]) -> tuple[str, str]:
    symbol_facts = {
        (context_ref, value.upper())
        for context_ref, value in facts.get("Symbol", [])
        if context_ref and value
    }
    if len(symbol_facts) != 1:
        raise EventParseError(
            "XBRL filing must contain one unambiguous Symbol fact and primary context"
        )
    return next(iter(symbol_facts))


def _xbrl_value(
    facts: dict[str, list[tuple[str, str]]],
    concept: str,
    context_ref: str,
    *,
    required: bool = False,
) -> str | None:
    values = {
        value
        for fact_context, value in facts.get(concept, [])
        if fact_context == context_ref and value
    }
    if len(values) > 1:
        raise EventParseError(
            f"conflicting XBRL facts for {concept} in context {context_ref}: {sorted(values)}"
        )
    if not values:
        if required:
            raise EventParseError(
                f"required XBRL fact missing: {concept} in context {context_ref}"
            )
        return None
    return next(iter(values))


def _xbrl_number(
    facts: dict[str, list[tuple[str, str]]], concept: str, context_ref: str
) -> float | None:
    return _parse_number(_xbrl_value(facts, concept, context_ref))


def parse_indas_xbrl(
    xml: str,
    *,
    source_url: str,
    raw_sha256: str,
    raw_path: str,
    captured_at_utc: str,
    mode: str = HISTORICAL_RECONSTRUCTION,
    exchange_published_at_utc: str | None = None,
    discovery_sha256: str | None = None,
    discovery_path: str | None = None,
    cohort_id: str | None = None,
    universe_rule_version: str | None = None,
    universe_snapshot_sha256: str | None = None,
) -> FinancialEvent:
    """Parse NSE's 2025 Integrated Filing Ind-AS XBRL instance format.

    The primary quarter is identified by the unique NSE Symbol fact's context. This
    avoids mixing quarter facts with YTD contexts such as FourD or dimensional contexts.
    """

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise EventParseError(f"filing is not well-formed XML: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise EventParseError("XML filing root is not an XBRL instance")

    facts = _xbrl_facts(root)
    primary_context, symbol = _xbrl_primary_context(facts)
    company_name = _xbrl_value(facts, "NameOfTheCompany", primary_context, required=True)
    basis = _xbrl_value(
        facts, "NatureOfReportStandaloneConsolidated", primary_context, required=True
    )
    reporting_period_end = _xbrl_value(
        facts, "DateOfEndOfReportingPeriod", primary_context, required=True
    )
    quarter = _xbrl_value(facts, "ReportingQuarter", primary_context, required=True)
    assert company_name is not None
    assert basis is not None
    assert reporting_period_end is not None
    assert quarter is not None
    event_id = _economic_event_id(symbol, reporting_period_end, basis, quarter)

    basic_eps = _xbrl_number(
        facts,
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        primary_context,
    )
    if basic_eps is None:
        basic_eps = _xbrl_number(
            facts, "BasicEarningsLossPerShareFromContinuingOperations", primary_context
        )
    diluted_eps = _xbrl_number(
        facts,
        "DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        primary_context,
    )
    if diluted_eps is None:
        diluted_eps = _xbrl_number(
            facts, "DilutedEarningsLossPerShareFromContinuingOperations", primary_context
        )

    provenance = _provenance(
        source_url=source_url,
        captured_at_utc=captured_at_utc,
        raw_sha256=raw_sha256,
        raw_path=raw_path,
        content_type="application/xml",
        source_mode="NSE_INTEGRATED_FILING_XBRL",
        exchange_published_at_utc=exchange_published_at_utc,
        discovery_sha256=discovery_sha256,
        discovery_path=discovery_path,
        cohort_id=cohort_id,
        universe_rule_version=universe_rule_version,
        universe_snapshot_sha256=universe_snapshot_sha256,
    )
    return FinancialEvent(
        schema_version=2 if mode == PROSPECTIVE else 1,
        parser_version=XBRL_PARSER_VERSION,
        mode=mode,
        economic_event_id=event_id,
        version_id=f"{event_id}-{raw_sha256[:12]}",
        symbol=symbol,
        isin=_xbrl_value(facts, "ISIN", primary_context),
        company_name=company_name,
        financial_year_start=_xbrl_value(facts, "DateOfStartOfFinancialYear", primary_context),
        financial_year_end=_xbrl_value(facts, "DateOfEndOfFinancialYear", primary_context),
        reporting_period_start=_xbrl_value(
            facts, "DateOfStartOfReportingPeriod", primary_context
        ),
        reporting_period_end=reporting_period_end,
        reporting_type=_xbrl_value(facts, "TypeOfReportingPeriod", primary_context),
        reporting_quarter=quarter,
        accounting_basis=basis,
        audited=_parse_audited(
            _xbrl_value(facts, "WhetherResultsAreAuditedOrUnaudited", primary_context)
        ),
        board_approval_date=_xbrl_value(
            facts, "DateOfBoardMeetingWhenFinancialResultsWereApproved", primary_context
        ),
        prior_intimation_date=_xbrl_value(
            facts,
            "DateOnWhichPriorIntimationOfTheMeetingForConsideringFinancialResultsWasInformedToTheExchange",
            primary_context,
        ),
        currency=_xbrl_value(facts, "DescriptionOfPresentationCurrency", primary_context),
        rounding=_xbrl_value(facts, "LevelOfRounding", primary_context),
        revenue_from_operations=_xbrl_number(facts, "RevenueFromOperations", primary_context),
        profit_before_exceptional_items_and_tax=_xbrl_number(
            facts, "ProfitBeforeExceptionalItemsAndTax", primary_context
        ),
        exceptional_items=_xbrl_number(facts, "ExceptionalItemsBeforeTax", primary_context),
        profit_before_tax=_xbrl_number(facts, "ProfitBeforeTax", primary_context),
        net_profit_continuing_operations=_xbrl_number(
            facts, "ProfitLossForPeriodFromContinuingOperations", primary_context
        ),
        total_profit=_xbrl_number(facts, "ProfitLossForPeriod", primary_context),
        basic_eps=basic_eps,
        diluted_eps=diluted_eps,
        operating_profit=None,
        operating_margin=None,
        unresolved_fields=_unresolved_fields(),
        provenance=provenance,
    )


def parse_indas_document(document: str, **kwargs: Any) -> FinancialEvent:
    """Dispatch an NSE Integrated Filing to XBRL or legacy HTML parsing."""

    stripped = document.lstrip("\ufeff\t\r\n ")
    if stripped.startswith("<?xml") or "<xbrli:xbrl" in stripped[:2048]:
        return parse_indas_xbrl(document, **kwargs)
    return parse_indas_html(document, **kwargs)


class EventStore:
    """Content-addressed local store for immutable filing and discovery bytes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _raw_path(self, digest: str, suffix: str) -> Path:
        return self.root / "raw" / "sha256" / f"{digest}{suffix}"

    def _discovery_path(self, digest: str) -> Path:
        return self.root / "discovery" / "sha256" / f"{digest}.json"

    def _record_path(self, event: FinancialEvent) -> Path:
        namespace = "prospective-events" if event.mode == PROSPECTIVE else "events"
        return self.root / namespace / event.economic_event_id / f"{event.provenance.raw_sha256}.json"

    @staticmethod
    def _write_content_addressed(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise RuntimeError("content-addressed store hash collision")
            return
        path.write_bytes(content)

    @staticmethod
    def _captured_at(captured_at: datetime | None) -> tuple[datetime, str]:
        captured_at = captured_at or datetime.now(UTC)
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        captured = captured_at.astimezone(UTC)
        return captured, captured.isoformat().replace("+00:00", "Z")

    def reconstruct_bytes(
        self,
        raw: bytes,
        *,
        source_url: str,
        suffix: str = ".html",
        captured_at: datetime | None = None,
    ) -> tuple[FinancialEvent, bool]:
        _, captured_at_utc = self._captured_at(captured_at)
        digest = sha256_bytes(raw)
        raw_path = self._raw_path(digest, suffix)
        self._write_content_addressed(raw_path, raw)

        document = raw.decode("utf-8", errors="strict")
        provisional = parse_indas_document(
            document,
            source_url=source_url,
            raw_sha256=digest,
            raw_path=str(raw_path),
            captured_at_utc=captured_at_utc,
            mode=HISTORICAL_RECONSTRUCTION,
        )
        record_path = self._record_path(provisional)
        if record_path.exists():
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            return _event_from_dict(existing), False

        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(provisional.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return provisional, True

    def capture_prospective_bytes(
        self,
        raw: bytes,
        *,
        discovery_bytes: bytes,
        source_url: str,
        exchange_published_at_utc: str,
        universe: UniverseSnapshot,
        suffix: str = ".html",
        captured_at: datetime | None = None,
        max_clock_skew_seconds: int = 300,
    ) -> tuple[FinancialEvent, bool]:
        """Capture a prospective filing with immutable discovery and universe provenance."""

        if not raw:
            raise EventParseError("prospective source bytes are empty")
        if not discovery_bytes:
            raise EventParseError("prospective discovery bytes are empty")
        try:
            discovery_payload = json.loads(discovery_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EventParseError(f"prospective discovery payload is not valid JSON: {exc}") from exc
        if not isinstance(discovery_payload, (dict, list)):
            raise EventParseError("prospective discovery payload must be JSON object or array")

        captured, captured_at_utc = self._captured_at(captured_at)
        published = _parse_utc_timestamp(
            exchange_published_at_utc, field="exchange_published_at_utc"
        )
        if published > captured + timedelta(seconds=max_clock_skew_seconds):
            raise EventParseError(
                "exchange publication timestamp is later than local capture time beyond tolerance"
            )
        universe_captured = _parse_utc_timestamp(
            universe.captured_at_utc, field="universe.captured_at_utc"
        )
        if universe_captured > published:
            raise EventParseError("universe snapshot was frozen after the filing was published")

        raw_digest = sha256_bytes(raw)
        raw_path = self._raw_path(raw_digest, suffix)
        self._write_content_addressed(raw_path, raw)
        discovery_digest = sha256_bytes(discovery_bytes)
        discovery_path = self._discovery_path(discovery_digest)
        self._write_content_addressed(discovery_path, discovery_bytes)

        document = raw.decode("utf-8", errors="strict")
        provisional = parse_indas_document(
            document,
            source_url=source_url,
            raw_sha256=raw_digest,
            raw_path=str(raw_path),
            captured_at_utc=captured_at_utc,
            mode=PROSPECTIVE,
            exchange_published_at_utc=published.isoformat().replace("+00:00", "Z"),
            discovery_sha256=discovery_digest,
            discovery_path=str(discovery_path),
            cohort_id=universe.cohort_id,
            universe_rule_version=universe.rule_version,
            universe_snapshot_sha256=universe.sha256,
        )
        if not universe.contains(provisional.symbol):
            raise EventParseError(
                f"symbol {provisional.symbol} is not eligible in frozen cohort {universe.cohort_id}"
            )
        matching_member = next(
            member for member in universe.members if member.symbol.upper() == provisional.symbol.upper()
        )
        if matching_member.isin and provisional.isin and matching_member.isin != provisional.isin:
            raise EventParseError(
                f"ISIN mismatch for {provisional.symbol}: universe={matching_member.isin}, "
                f"filing={provisional.isin}"
            )

        record_path = self._record_path(provisional)
        if record_path.exists():
            existing = _event_from_dict(json.loads(record_path.read_text(encoding="utf-8")))
            if (
                existing.provenance.discovery_sha256 != discovery_digest
                or existing.provenance.exchange_published_at_utc
                != provisional.provenance.exchange_published_at_utc
                or existing.provenance.universe_snapshot_sha256 != universe.sha256
            ):
                raise EventParseError(
                    "same filing bytes already exist with conflicting prospective provenance"
                )
            return existing, False

        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(provisional.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return provisional, True


def _event_from_dict(payload: dict[str, Any]) -> FinancialEvent:
    payload = dict(payload)
    provenance = SourceProvenance(**payload.pop("provenance"))
    unresolved = tuple(payload.pop("unresolved_fields", []))
    return FinancialEvent(**payload, unresolved_fields=unresolved, provenance=provenance)
