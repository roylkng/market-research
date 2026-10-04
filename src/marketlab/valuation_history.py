from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from marketlab.alpha import AlphaContractError
from marketlab.alpha_fundamental import (
    BASIS_PREFERENCE,
    FilingCandidate,
    _candidate_rows,
    _legacy_candidate_rows,
    _unique_at_timestamp,
    monetary_scale,
    normalized_monetary_facts,
)
from marketlab.events import HISTORICAL_RECONSTRUCTION, parse_indas_document, sha256_bytes

VQ001_D001_ID = "VQ001-D001-v1"
CURRENT_VALUATION_SESSION = "2026-10-01"
SNAPSHOT_QUARTERS = {
    "2025-09-30": ("2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30"),
    "2025-12-31": ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"),
    "2026-03-31": ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"),
    "2026-06-30": ("2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"),
}
BENGALURU_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class SelectedPeriodFiling:
    candidate: FilingCandidate
    source_family: str


@dataclass(frozen=True)
class QuarterlyValuationFacts:
    symbol: str
    isin: str | None
    accounting_basis: str
    period_end: str
    published_at_utc: str
    source_url: str
    raw_sha256: str
    total_profit_inr: float | None
    paid_up_equity_share_capital_inr: float | None
    face_value_per_share_inr: float | None
    equity_share_capital_inr: float | None
    share_count: float | None


def _normalise(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_number(value: object) -> float | None:
    raw = _normalise(value)
    if not raw or raw.casefold() in {"-", "--", "na", "n/a", "null"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    raw = raw.replace(",", "").replace("₹", "").strip()
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return -parsed if negative else parsed


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _xbrl_contexts(root: ET.Element) -> dict[str, dict[str, object]]:
    contexts: dict[str, dict[str, object]] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        instant = None
        dimensional = False
        for child in element.iter():
            name = _local_name(child.tag)
            if name == "instant":
                instant = _normalise(child.text)
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        contexts[context_id] = {
            "instant": instant,
            "dimensional": dimensional,
        }
    return contexts


def _xbrl_facts(root: ET.Element) -> dict[str, list[tuple[str, str]]]:
    facts: dict[str, list[tuple[str, str]]] = {}
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        value = _normalise(element.text)
        if not value:
            continue
        facts.setdefault(_local_name(element.tag).casefold(), []).append(
            (context_ref, value)
        )
    return facts


def _unique_numeric(
    facts: dict[str, list[tuple[str, str]]],
    concept: str,
    *,
    context_ids: set[str] | None = None,
) -> float | None:
    values: set[float] = set()
    for context_ref, raw in facts.get(concept.casefold(), []):
        if context_ids is not None and context_ref not in context_ids:
            continue
        parsed = _parse_number(raw)
        if parsed is not None:
            values.add(parsed)
    if len(values) > 1:
        raise AlphaContractError(
            f"VQ001 conflicting XBRL values for {concept}: {sorted(values)}"
        )
    return next(iter(values)) if values else None


def _html_rows(document: str) -> list[list[str]]:
    soup = BeautifulSoup(document, "html.parser")
    rows: list[list[str]] = []
    for row in soup.find_all("tr"):
        cells = [_normalise(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    return rows


def _html_number(rows: list[list[str]], labels: tuple[str, ...]) -> float | None:
    wanted = {_normalise(label).casefold() for label in labels}
    values: list[float] = []
    for cells in rows:
        lowered = [_normalise(cell).casefold() for cell in cells]
        for index, cell in enumerate(lowered):
            if cell not in wanted:
                continue
            for raw in cells[index + 1 :]:
                parsed = _parse_number(raw)
                if parsed is not None:
                    values.append(parsed)
    return values[-1] if values else None


def select_period_filing(
    integrated_payload: object,
    legacy_payload: object,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> SelectedPeriodFiling:
    integrated = _candidate_rows(
        integrated_payload,
        symbol=symbol,
        period_end=period_end,
        accounting_basis=accounting_basis,
    )
    if integrated:
        return SelectedPeriodFiling(
            candidate=_unique_at_timestamp(integrated, use_first=True),
            source_family="INTEGRATED",
        )

    legacy = _legacy_candidate_rows(
        legacy_payload,
        symbol=symbol,
        period_end=period_end,
        accounting_basis=accounting_basis,
    )
    if legacy:
        return SelectedPeriodFiling(
            candidate=_unique_at_timestamp(legacy, use_first=True),
            source_family="LEGACY",
        )

    raise AlphaContractError(
        f"VQ001 no filing for {symbol} {period_end} {accounting_basis}"
    )


def select_snapshot_filings(
    integrated_payload: object,
    legacy_payload: object,
    *,
    symbol: str,
    required_periods: tuple[str, ...],
) -> tuple[str, dict[str, SelectedPeriodFiling]]:
    for basis in BASIS_PREFERENCE:
        selected: dict[str, SelectedPeriodFiling] = {}
        try:
            for period_end in required_periods:
                selected[period_end] = select_period_filing(
                    integrated_payload,
                    legacy_payload,
                    symbol=symbol,
                    period_end=period_end,
                    accounting_basis=basis,
                )
        except AlphaContractError:
            continue
        return basis, selected
    raise AlphaContractError(
        f"VQ001 no complete four-quarter same-basis filing set for {symbol}"
    )


def _parse_share_facts_xbrl(
    document: str,
    *,
    period_end: str,
) -> tuple[float | None, float | None, float | None]:
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise AlphaContractError(f"VQ001 filing is not well-formed XML: {exc}") from exc
    contexts = _xbrl_contexts(root)
    facts = _xbrl_facts(root)

    symbol_contexts = {
        context_ref
        for context_ref, value in facts.get("symbol", [])
        if _normalise(value)
    }
    paid_up = _unique_numeric(
        facts,
        "PaidUpValueOfEquityShareCapital",
        context_ids=symbol_contexts if symbol_contexts else None,
    )
    face_value = _unique_numeric(
        facts,
        "FaceValueOfEquityShareCapital",
        context_ids=symbol_contexts if symbol_contexts else None,
    )
    instant_contexts = {
        context_id
        for context_id, row in contexts.items()
        if row["dimensional"] is False and row["instant"] == period_end
    }
    equity_capital = _unique_numeric(
        facts,
        "EquityShareCapital",
        context_ids=instant_contexts if instant_contexts else None,
    )
    return paid_up, face_value, equity_capital


def _parse_share_facts_html(
    document: str,
) -> tuple[float | None, float | None, float | None]:
    rows = _html_rows(document)
    paid_up = _html_number(
        rows,
        (
            "Paid-up equity share capital",
            "Paid up equity share capital",
            "Paid-up value of equity share capital",
        ),
    )
    face_value = _html_number(
        rows,
        (
            "Face value of equity share capital",
            "Face value of equity share",
        ),
    )
    equity_capital = _html_number(rows, ("Equity share capital",))
    return paid_up, face_value, equity_capital


def parse_quarterly_valuation_filing(
    raw: bytes,
    *,
    candidate: FilingCandidate,
) -> QuarterlyValuationFacts:
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("VQ001 filing bytes are not UTF-8") from exc

    event = parse_indas_document(
        document,
        source_url=candidate.source_url,
        raw_sha256=sha256_bytes(raw),
        raw_path="VQ001_CONTENT_ADDRESSED",
        captured_at_utc=candidate.exchange_published_at_utc,
        mode=HISTORICAL_RECONSTRUCTION,
        exchange_published_at_utc=candidate.exchange_published_at_utc,
    )
    if event.reporting_period_end != candidate.period_end:
        raise AlphaContractError("VQ001 parsed filing period mismatch")
    if event.accounting_basis.casefold() != candidate.accounting_basis.casefold():
        raise AlphaContractError("VQ001 parsed filing accounting-basis mismatch")

    total_profit = normalized_monetary_facts(event)["total_profit"]

    stripped = document.lstrip("\ufeff\t\r\n ")
    if stripped.startswith("<?xml") or "<xbrli:xbrl" in stripped[:4096]:
        paid_up, face_value, equity_capital = _parse_share_facts_xbrl(
            document,
            period_end=candidate.period_end,
        )
    else:
        paid_up, face_value, equity_capital = _parse_share_facts_html(document)
        if paid_up is not None:
            paid_up *= monetary_scale(event)
        if equity_capital is not None:
            equity_capital *= monetary_scale(event)

    share_count = None
    if paid_up is not None and face_value is not None:
        if paid_up <= 0 or face_value <= 0:
            raise AlphaContractError("VQ001 paid-up capital and face value must be positive")
        share_count = paid_up / face_value
        if not math.isfinite(share_count) or share_count <= 0:
            raise AlphaContractError("VQ001 derived share count must be positive")
        if equity_capital is not None and equity_capital > 0:
            relative_gap = abs(paid_up - equity_capital) / max(
                abs(paid_up),
                abs(equity_capital),
            )
            if relative_gap > 0.001:
                raise AlphaContractError(
                    "VQ001 paid-up capital disagrees with equity share capital"
                )

    return QuarterlyValuationFacts(
        symbol=event.symbol.upper(),
        isin=event.isin,
        accounting_basis=event.accounting_basis,
        period_end=event.reporting_period_end,
        published_at_utc=candidate.exchange_published_at_utc,
        source_url=candidate.source_url,
        raw_sha256=event.provenance.raw_sha256,
        total_profit_inr=total_profit,
        paid_up_equity_share_capital_inr=paid_up,
        face_value_per_share_inr=face_value,
        equity_share_capital_inr=equity_capital,
        share_count=share_count,
    )


def _published_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise AlphaContractError(f"VQ001 invalid filing timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("VQ001 filing timestamp must include timezone")
    return parsed.astimezone(UTC)


def validate_snapshot_issuer_identity(
    *,
    frozen_symbol: str,
    frozen_isin: str | None,
    target: QuarterlyValuationFacts,
    components: list[QuarterlyValuationFacts],
    bridge_index: dict[str, dict[str, str]],
    as_of_date: str,
) -> str:
    if not frozen_isin:
        raise AlphaContractError("VQ001 frozen universe ISIN is required")
    if not target.isin:
        raise AlphaContractError("VQ001 target filing ISIN is required")

    bridge = bridge_index.get(frozen_symbol.upper())
    target_time = _published_date(target.published_at_utc)
    as_of = datetime.fromisoformat(as_of_date).replace(tzinfo=UTC)

    if target.isin == frozen_isin:
        target_state = "TARGET_MATCHES_FROZEN_ISIN"
    elif (
        bridge is not None
        and target.isin == bridge["old_isin"]
        and frozen_isin == bridge["new_isin"]
    ):
        effective = datetime.fromisoformat(bridge["effective_date"]).replace(tzinfo=UTC)
        if not target_time < effective <= as_of:
            raise AlphaContractError(
                "VQ001 target-to-frozen ISIN bridge date is inconsistent"
            )
        target_state = "TARGET_PRECEDES_VERIFIED_NSE_ISIN_BRIDGE"
    else:
        raise AlphaContractError("VQ001 target filing cannot be linked to frozen issuer")

    for component in components:
        if not component.isin:
            raise AlphaContractError("VQ001 component filing ISIN is required")
        if component.isin == target.isin:
            continue
        if bridge is None:
            raise AlphaContractError("VQ001 component has unverified ISIN transition")
        if component.isin != bridge["old_isin"] or target.isin != bridge["new_isin"]:
            raise AlphaContractError("VQ001 component ISINs do not match frozen bridge")
        component_time = _published_date(component.published_at_utc)
        effective = datetime.fromisoformat(bridge["effective_date"]).replace(tzinfo=UTC)
        if not component_time < effective <= target_time:
            raise AlphaContractError(
                "VQ001 component-to-target ISIN bridge date is inconsistent"
            )

    return target_state

def publication_market_date(published_at_utc: str) -> str:
    try:
        parsed = datetime.fromisoformat(published_at_utc)
    except ValueError as exc:
        raise AlphaContractError(
            f"VQ001 invalid publication timestamp: {published_at_utc}"
        ) from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("VQ001 publication timestamp must include timezone")
    return parsed.astimezone(BENGALURU_TZ).date().isoformat()


def compute_ttm_pe_proxy(
    *,
    quarterly_profits_inr: list[float],
    share_count: float,
    price_inr: float,
) -> dict[str, float]:
    if len(quarterly_profits_inr) != 4:
        raise AlphaContractError("VQ001 TTM P/E requires exactly four quarterly profits")
    if any(not math.isfinite(value) for value in quarterly_profits_inr):
        raise AlphaContractError("VQ001 TTM profit contains nonfinite value")
    ttm_profit = sum(quarterly_profits_inr)
    if ttm_profit <= 0:
        raise AlphaContractError("VQ001 TTM PAT must be strictly positive")
    if not math.isfinite(share_count) or share_count <= 0:
        raise AlphaContractError("VQ001 share count must be strictly positive")
    if not math.isfinite(price_inr) or price_inr <= 0:
        raise AlphaContractError("VQ001 price must be strictly positive")

    market_cap = price_inr * share_count
    pe = market_cap / ttm_profit
    if not math.isfinite(market_cap) or market_cap <= 0:
        raise AlphaContractError("VQ001 market cap must be positive")
    if not math.isfinite(pe) or pe <= 0:
        raise AlphaContractError("VQ001 TTM P/E must be positive")

    return {
        "ttm_profit_inr": ttm_profit,
        "share_count": share_count,
        "price_inr": price_inr,
        "market_cap_inr": market_cap,
        "ttm_pe_proxy": pe,
        "earnings_yield_proxy": 1.0 / pe,
    }
