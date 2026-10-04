from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_fundamental import FilingCandidate, FundamentalPair
from marketlab.events import sha256_bytes

FQ001_D001_ID = "FQ001-D001-v1"
TARGET_PERIOD_END = "2026-03-31"
BASELINE_PERIOD_END = "2025-03-31"
PARSER_HTML = "fq001-indas-html-v1"
PARSER_XBRL = "fq001-indas-xbrl-v1"

CORE_METRICS = (
    "roce_proxy",
    "cfo_to_pat",
    "cfo_minus_ppe_to_pat",
    "accruals_to_avg_assets",
    "net_borrowings_to_equity",
    "ppe_capex_to_revenue",
)

FACT_FIELDS = (
    "revenue",
    "profit_before_tax",
    "finance_costs",
    "profit_after_tax",
    "total_assets",
    "total_equity",
    "current_liabilities",
    "cash_and_cash_equivalents",
    "borrowings_current",
    "borrowings_noncurrent",
    "operating_cash_flow",
    "purchase_ppe",
)

HTML_LABELS = {
    "revenue": "Revenue from operations",
    "profit_before_tax": "Total profit before tax",
    "finance_costs": "Finance costs",
    "profit_after_tax": "Total profit (loss) for period",
    "total_assets": "Total assets",
    "total_equity": "Total equity",
    "current_liabilities": "Total current liabilities",
    "cash_and_cash_equivalents": "Cash and cash equivalents",
    "borrowings_current": "Borrowings, current",
    "borrowings_noncurrent": "Borrowings, non-current",
    "operating_cash_flow": "Net cash flows from (used in) operating activities",
    "purchase_ppe": "Purchase of property, plant and equipment",
}

XBRL_ALIASES = {
    "revenue": ("RevenueFromOperations",),
    "profit_before_tax": ("ProfitBeforeTax",),
    "finance_costs": ("FinanceCosts", "FinanceCost"),
    "profit_after_tax": ("ProfitLossForPeriod",),
    "total_assets": ("TotalAssets", "Assets"),
    "total_equity": ("TotalEquity", "Equity"),
    "current_liabilities": ("TotalCurrentLiabilities", "CurrentLiabilities"),
    "cash_and_cash_equivalents": (
        "CashAndCashEquivalents",
        "CashAndCashEquivalentsCashFlowStatement",
    ),
    "borrowings_current": ("BorrowingsCurrent", "CurrentBorrowings"),
    "borrowings_noncurrent": (
        "BorrowingsNoncurrent",
        "BorrowingsNonCurrent",
        "NoncurrentBorrowings",
        "NonCurrentBorrowings",
    ),
    "operating_cash_flow": (
        "NetCashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ),
    "purchase_ppe": (
        "PurchaseOfPropertyPlantAndEquipment",
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ),
}

_NUMBER_CLEAN_RE = re.compile(r"[₹,\s]")


@dataclass(frozen=True)
class AnnualQualityFacts:
    parser_version: str
    symbol: str
    isin: str | None
    company_name: str | None
    accounting_basis: str
    financial_year_start: str
    period_end: str
    currency: str
    rounding: str | None
    raw_sha256: str
    source_url: str
    facts: dict[str, float | None]


@dataclass(frozen=True)
class _XbrlContext:
    context_id: str
    start_date: str | None
    end_date: str | None
    instant: str | None
    dimensional: bool


def _normalise(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_number(value: object) -> float | None:
    text = _normalise(value)
    if not text or text.casefold() in {"null", "na", "n/a", "-", "--"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    text = _NUMBER_CLEAN_RE.sub("", text)
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return -number if negative else number


def _parse_date(value: object) -> str | None:
    raw = _normalise(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _currency_is_inr(value: object) -> bool:
    return _normalise(value).casefold() in {
        "inr",
        "indian rupee",
        "indian rupees",
        "rs",
        "rs.",
        "rupee",
        "rupees",
    }


def _html_scale(rounding: str | None) -> float:
    raw = _normalise(rounding).casefold()
    if any(token in raw for token in ("crore", "crores")):
        return 10_000_000.0
    if any(token in raw for token in ("lakh", "lakhs", "lac", "lacs")):
        return 100_000.0
    if any(token in raw for token in ("million", "millions")):
        return 1_000_000.0
    if any(token in raw for token in ("thousand", "thousands")):
        return 1_000.0
    if any(token in raw for token in ("actual", "rupee", "unit")):
        return 1.0
    raise AlphaContractError(f"FQ001 unsupported HTML rounding metadata: {rounding}")


def _html_rows(document: str) -> list[list[str]]:
    soup = BeautifulSoup(document, "html.parser")
    rows = []
    for row in soup.find_all("tr"):
        cells = [_normalise(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    return rows


def _html_exact_values(rows: list[list[str]], label: str) -> list[str]:
    wanted = _normalise(label).casefold()
    values = []
    for cells in rows:
        lowered = [_normalise(cell).casefold() for cell in cells]
        for index, cell in enumerate(lowered):
            if cell != wanted:
                continue
            values.extend(value for value in cells[index + 1 :] if _normalise(value))
    return values


def _html_last_text(rows: list[list[str]], label: str) -> str | None:
    values = _html_exact_values(rows, label)
    return values[-1] if values else None


def _html_last_number(rows: list[list[str]], label: str) -> float | None:
    values = _html_exact_values(rows, label)
    numbers = [_parse_number(value) for value in values]
    numeric = [value for value in numbers if value is not None]
    return numeric[-1] if numeric else None


def _require_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise AlphaContractError(f"FQ001 required filing field missing: {label}")
    return value.strip()


def _parse_html_quality(document: str, *, source_url: str, raw_sha256: str) -> AnnualQualityFacts:
    rows = _html_rows(document)
    if not rows:
        raise AlphaContractError("FQ001 filing contains no HTML table rows")

    symbol = _require_text(_html_last_text(rows, "NSE Symbol"), "NSE Symbol").upper()
    basis = _require_text(
        _html_last_text(rows, "Nature of report standalone or consolidated"),
        "accounting basis",
    )
    period_end = _parse_date(_html_last_text(rows, "Date of end of financial year"))
    financial_year_start = _parse_date(_html_last_text(rows, "Date of start of financial year"))
    currency = _require_text(
        _html_last_text(rows, "Description of presentation currency"),
        "presentation currency",
    )
    rounding = _html_last_text(rows, "Level of rounding used in financial results")
    if period_end is None or financial_year_start is None:
        raise AlphaContractError("FQ001 HTML financial-year dates are unavailable")
    if not _currency_is_inr(currency):
        raise AlphaContractError(f"FQ001 unsupported presentation currency: {currency}")
    scale = _html_scale(rounding)

    facts = {}
    for field, label in HTML_LABELS.items():
        raw = _html_last_number(rows, label)
        facts[field] = None if raw is None else raw * scale

    return AnnualQualityFacts(
        parser_version=PARSER_HTML,
        symbol=symbol,
        isin=_html_last_text(rows, "ISIN"),
        company_name=_html_last_text(rows, "Name of company"),
        accounting_basis=basis,
        financial_year_start=financial_year_start,
        period_end=period_end,
        currency=currency,
        rounding=rounding,
        raw_sha256=raw_sha256,
        source_url=source_url,
        facts=facts,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _xbrl_contexts(root: ET.Element) -> dict[str, _XbrlContext]:
    contexts = {}
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
            text = _normalise(child.text)
            if name == "startDate":
                start_date = _parse_date(text)
            elif name == "endDate":
                end_date = _parse_date(text)
            elif name == "instant":
                instant = _parse_date(text)
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        contexts[context_id] = _XbrlContext(
            context_id=context_id,
            start_date=start_date,
            end_date=end_date,
            instant=instant,
            dimensional=dimensional,
        )
    return contexts


def _xbrl_facts(root: ET.Element) -> dict[str, list[tuple[str, str]]]:
    facts: dict[str, list[tuple[str, str]]] = {}
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        text = _normalise(element.text)
        if not text:
            continue
        key = _local_name(element.tag).casefold()
        facts.setdefault(key, []).append((context_ref, text))
    return facts


def _xbrl_text(
    facts: dict[str, list[tuple[str, str]]],
    aliases: tuple[str, ...],
    context_ids: set[str] | None = None,
) -> str | None:
    values = set()
    for alias in aliases:
        for context_ref, value in facts.get(alias.casefold(), []):
            if context_ids is not None and context_ref not in context_ids:
                continue
            values.add(value)
    if len(values) > 1:
        raise AlphaContractError(
            f"FQ001 conflicting XBRL text facts for aliases={aliases}: {sorted(values)}"
        )
    return next(iter(values)) if values else None


def _xbrl_number_for_contexts(
    facts: dict[str, list[tuple[str, str]]],
    aliases: tuple[str, ...],
    context_ids: set[str],
) -> float | None:
    values = set()
    for alias in aliases:
        for context_ref, raw in facts.get(alias.casefold(), []):
            if context_ref not in context_ids:
                continue
            value = _parse_number(raw)
            if value is not None:
                values.add(value)
    if len(values) > 1:
        raise AlphaContractError(
            f"FQ001 conflicting XBRL numeric facts for aliases={aliases}: {sorted(values)}"
        )
    return next(iter(values)) if values else None


def _parse_xml_quality(document: str, *, source_url: str, raw_sha256: str) -> AnnualQualityFacts:
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise AlphaContractError(f"FQ001 filing is not well-formed XML: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise AlphaContractError("FQ001 XML filing root is not XBRL")

    contexts = _xbrl_contexts(root)
    facts = _xbrl_facts(root)
    symbol_entries = facts.get("symbol", [])
    symbol_values = {value.upper() for _, value in symbol_entries}
    if len(symbol_values) != 1:
        raise AlphaContractError("FQ001 XBRL symbol is not unambiguous")
    symbol = next(iter(symbol_values))
    symbol_contexts = {context_ref for context_ref, _ in symbol_entries}

    fy_start = _parse_date(
        _xbrl_text(facts, ("DateOfStartOfFinancialYear",), symbol_contexts)
    )
    period_end = _parse_date(
        _xbrl_text(facts, ("DateOfEndOfFinancialYear",), symbol_contexts)
    )
    basis = _xbrl_text(
        facts,
        ("NatureOfReportStandaloneConsolidated",),
        symbol_contexts,
    )
    currency = _xbrl_text(
        facts,
        ("DescriptionOfPresentationCurrency",),
        symbol_contexts,
    )
    if fy_start is None or period_end is None:
        raise AlphaContractError("FQ001 XBRL financial-year dates are unavailable")
    if basis is None:
        raise AlphaContractError("FQ001 XBRL accounting basis is unavailable")
    if currency is None or not _currency_is_inr(currency):
        raise AlphaContractError(f"FQ001 unsupported presentation currency: {currency}")

    annual_contexts = {
        context_id
        for context_id, context in contexts.items()
        if not context.dimensional
        and context.start_date == fy_start
        and context.end_date == period_end
    }
    instant_contexts = {
        context_id
        for context_id, context in contexts.items()
        if not context.dimensional and context.instant == period_end
    }
    if not annual_contexts:
        raise AlphaContractError("FQ001 XBRL annual duration context is unavailable")
    if not instant_contexts:
        raise AlphaContractError("FQ001 XBRL year-end instant context is unavailable")

    duration_fields = {
        "revenue",
        "profit_before_tax",
        "finance_costs",
        "profit_after_tax",
        "operating_cash_flow",
        "purchase_ppe",
    }
    facts_out = {}
    for field in FACT_FIELDS:
        contexts_for_field = annual_contexts if field in duration_fields else instant_contexts
        facts_out[field] = _xbrl_number_for_contexts(
            facts,
            XBRL_ALIASES[field],
            contexts_for_field,
        )

    return AnnualQualityFacts(
        parser_version=PARSER_XBRL,
        symbol=symbol,
        isin=_xbrl_text(facts, ("ISIN",), symbol_contexts),
        company_name=_xbrl_text(facts, ("NameOfTheCompany",), symbol_contexts),
        accounting_basis=basis,
        financial_year_start=fy_start,
        period_end=period_end,
        currency=currency,
        rounding=_xbrl_text(facts, ("LevelOfRounding",), symbol_contexts),
        raw_sha256=raw_sha256,
        source_url=source_url,
        facts=facts_out,
    )


def parse_annual_quality_filing(
    raw: bytes,
    *,
    candidate: FilingCandidate,
) -> AnnualQualityFacts:
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("FQ001 filing bytes are not UTF-8") from exc

    stripped = document.lstrip("\ufeff\t\r\n ")
    raw_sha = sha256_bytes(raw)
    if stripped.startswith("<?xml") or "<xbrli:xbrl" in stripped[:4096]:
        parsed = _parse_xml_quality(
            document,
            source_url=candidate.source_url,
            raw_sha256=raw_sha,
        )
    else:
        parsed = _parse_html_quality(
            document,
            source_url=candidate.source_url,
            raw_sha256=raw_sha,
        )

    if parsed.symbol.upper() != candidate.symbol.upper():
        raise AlphaContractError("FQ001 parsed filing symbol mismatch")
    if parsed.period_end != candidate.period_end:
        raise AlphaContractError(
            f"FQ001 parsed annual period mismatch: {parsed.period_end} != {candidate.period_end}"
        )
    if (
        parsed.accounting_basis.strip().casefold()
        != candidate.accounting_basis.strip().casefold()
    ):
        raise AlphaContractError("FQ001 parsed filing basis mismatch")
    return parsed


def _finite_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = numerator / denominator
    return float(value) if math.isfinite(value) else None


def build_quality_metrics(
    *,
    target: AnnualQualityFacts,
    baseline: AnnualQualityFacts,
) -> dict[str, float | None]:
    if target.symbol.upper() != baseline.symbol.upper():
        raise AlphaContractError("FQ001 target/baseline symbol mismatch")
    if target.accounting_basis.casefold() != baseline.accounting_basis.casefold():
        raise AlphaContractError("FQ001 target/baseline accounting basis mismatch")
    if target.period_end != TARGET_PERIOD_END or baseline.period_end != BASELINE_PERIOD_END:
        raise AlphaContractError("FQ001 annual period pair mismatch")

    t = target.facts
    b = baseline.facts
    pbt = t["profit_before_tax"]
    finance = t["finance_costs"]
    pat = t["profit_after_tax"]
    cfo = t["operating_cash_flow"]
    ppe = t["purchase_ppe"]
    revenue = t["revenue"]

    ebit = None if pbt is None or finance is None else pbt + finance
    ce_t = (
        None
        if t["total_assets"] is None or t["current_liabilities"] is None
        else t["total_assets"] - t["current_liabilities"]
    )
    ce_b = (
        None
        if b["total_assets"] is None or b["current_liabilities"] is None
        else b["total_assets"] - b["current_liabilities"]
    )
    avg_ce = None if ce_t is None or ce_b is None else (ce_t + ce_b) / 2.0
    avg_assets = (
        None
        if t["total_assets"] is None or b["total_assets"] is None
        else (t["total_assets"] + b["total_assets"]) / 2.0
    )

    net_borrowings = None
    if all(
        t[field] is not None
        for field in (
            "borrowings_current",
            "borrowings_noncurrent",
            "cash_and_cash_equivalents",
        )
    ):
        net_borrowings = (
            t["borrowings_current"]
            + t["borrowings_noncurrent"]
            - t["cash_and_cash_equivalents"]
        )

    cfo_minus_ppe = None if cfo is None or ppe is None else cfo - abs(ppe)
    accruals = None if pat is None or cfo is None else pat - cfo

    return {
        "roce_proxy": _finite_ratio(ebit, avg_ce),
        "cfo_to_pat": _finite_ratio(cfo, pat),
        "cfo_minus_ppe_to_pat": _finite_ratio(cfo_minus_ppe, pat),
        "accruals_to_avg_assets": _finite_ratio(accruals, avg_assets),
        "net_borrowings_to_equity": _finite_ratio(net_borrowings, t["total_equity"]),
        "ppe_capex_to_revenue": _finite_ratio(abs(ppe) if ppe is not None else None, revenue),
    }


def quality_record(
    *,
    pair: FundamentalPair,
    target: AnnualQualityFacts,
    baseline: AnnualQualityFacts,
    discovery_raw_sha256: str,
) -> dict:
    metrics = build_quality_metrics(target=target, baseline=baseline)
    complete_count = sum(metrics[name] is not None for name in CORE_METRICS)
    record = {
        "schema_version": 1,
        "diagnostic_id": FQ001_D001_ID,
        "symbol": pair.symbol,
        "accounting_basis": pair.accounting_basis,
        "target_period_end": target.period_end,
        "baseline_period_end": baseline.period_end,
        "target_exchange_published_at_utc": pair.target.exchange_published_at_utc,
        "baseline_exchange_published_at_utc": pair.baseline.exchange_published_at_utc,
        "target_source_url": pair.target.source_url,
        "baseline_source_url": pair.baseline.source_url,
        "target_raw_sha256": target.raw_sha256,
        "baseline_raw_sha256": baseline.raw_sha256,
        "discovery_raw_sha256": discovery_raw_sha256,
        "target_parser_version": target.parser_version,
        "baseline_parser_version": baseline.parser_version,
        "target_facts": target.facts,
        "baseline_facts": baseline.facts,
        "metrics": metrics,
        "complete_metric_count": complete_count,
        "all_core_metrics_complete": complete_count == len(CORE_METRICS),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    record["record_sha256"] = digest(record)
    return record


def select_annual_quality_pair(payload: object, *, symbol: str) -> FundamentalPair:
    from marketlab.alpha_fundamental import select_fundamental_pair

    return select_fundamental_pair(
        payload,
        symbol=symbol,
        target_period_end=TARGET_PERIOD_END,
        baseline_period_end=BASELINE_PERIOD_END,
    )


def fiscal_year_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def validate_annual_shape(facts: AnnualQualityFacts) -> None:
    days = fiscal_year_days(facts.financial_year_start, facts.period_end)
    if days < 350 or days > 380:
        raise AlphaContractError(f"FQ001 filing is not annual-length: {days} days")
    for name, value in facts.facts.items():
        if value is not None and not math.isfinite(value):
            raise AlphaContractError(f"FQ001 nonfinite fact {name}")
