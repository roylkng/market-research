from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import (
    HISTORICAL_RECONSTRUCTION,
    PARSER_VERSION,
    XBRL_PARSER_VERSION,
    FinancialEvent,
    parse_indas_document,
    sha256_bytes,
)

T008_D001_ID = "AE001-T008-D001-v1"
TARGET_PERIOD_END = "2026-06-30"
BASELINE_PERIOD_END = "2025-06-30"
BASIS_PREFERENCE = ("Consolidated", "Standalone")
FEATURE_NAMES = (
    "revenue_yoy",
    "pbt_change_to_prior_revenue",
    "total_profit_change_to_prior_revenue",
    "pbt_margin",
    "pbt_margin_delta_yoy",
    "total_profit_margin_delta_yoy",
)


@dataclass(frozen=True)
class FilingCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    discovery_row_sha256: str
    discovery_row: dict[str, Any]


@dataclass(frozen=True)
class FundamentalPair:
    symbol: str
    accounting_basis: str
    target: FilingCandidate
    baseline: FilingCandidate


def _rows(payload: object) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise AlphaContractError(
            "T008 integrated filing discovery payload lacks a data list"
        )
    return [row for row in rows if isinstance(row, dict)]


def _parse_exchange_time(value: object) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise AlphaContractError("T008 filing publication timestamp is missing")
    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    except ValueError:
        pass

    formats = (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(f"{raw} +0530", f"{fmt} %z")
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    raise AlphaContractError(
        f"T008 unsupported filing publication timestamp: {raw}"
    )


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _period_iso(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _candidate_rows(
    payload: object,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[FilingCandidate]:
    wanted_symbol = symbol.strip().upper()
    wanted_basis = accounting_basis.strip().casefold()
    candidates = []
    for row in _rows(payload):
        if (
            str(row.get("type") or "").strip().casefold()
            != "integrated filing- financials"
        ):
            continue
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        if str(row.get("consolidated") or "").strip().casefold() != wanted_basis:
            continue
        if _period_iso(row.get("qe_Date")) != period_end:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url:
            continue
        available_raw = (
            row.get("broadcast_Date")
            or row.get("revised_Date")
            or row.get("creation_Date")
        )
        try:
            available = _parse_exchange_time(available_raw)
        except AlphaContractError:
            continue
        candidates.append(
            FilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=accounting_basis,
                period_end=period_end,
                exchange_published_at_utc=_iso_utc(available),
                source_url=source_url,
                discovery_row_sha256=digest(row),
                discovery_row=dict(row),
            )
        )
    candidates.sort(
        key=lambda item: (
            item.exchange_published_at_utc,
            item.source_url,
        )
    )
    return candidates


def _legacy_basis(value: object) -> str | None:
    raw = " ".join(
        str(value or "")
        .strip()
        .casefold()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )
    if raw == "consolidated":
        return "Consolidated"
    if raw in {
        "standalone",
        "non consolidated",
        "nonconsolidated",
    }:
        return "Standalone"
    return None


def _legacy_candidate_rows(
    payload: object,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[FilingCandidate]:
    """Normalize legacy /api/corporates-financial-results rows."""

    wanted_symbol = symbol.strip().upper()
    candidates = []
    for row in _rows(payload):
        if str(row.get("symbol") or "").strip().upper() != wanted_symbol:
            continue
        basis = _legacy_basis(row.get("consolidated"))
        if basis != accounting_basis:
            continue
        period_raw = (
            row.get("toDate")
            or row.get("to_Date")
            or row.get("periodEnded")
            or row.get("period_end")
        )
        if _period_iso(period_raw) != period_end:
            continue
        source_url = str(row.get("xbrl") or "").strip()
        if not source_url or source_url in {"-", "--"}:
            continue
        available_raw = (
            row.get("broadCastDate")
            or row.get("broadcastDate")
            or row.get("broadcast_Date")
            or row.get("filingDate")
            or row.get("filing_Date")
        )
        try:
            available = _parse_exchange_time(available_raw)
        except AlphaContractError:
            continue
        candidates.append(
            FilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=accounting_basis,
                period_end=period_end,
                exchange_published_at_utc=_iso_utc(available),
                source_url=source_url,
                discovery_row_sha256=digest(row),
                discovery_row=dict(row),
            )
        )
    candidates.sort(
        key=lambda item: (
            item.exchange_published_at_utc,
            item.source_url,
        )
    )
    return candidates


def _unique_at_timestamp(
    candidates: list[FilingCandidate],
    *,
    use_first: bool,
) -> FilingCandidate:
    if not candidates:
        raise AlphaContractError("T008 filing candidate set is empty")
    wanted_time = (
        candidates[0].exchange_published_at_utc
        if use_first
        else candidates[-1].exchange_published_at_utc
    )
    rows = [
        candidate
        for candidate in candidates
        if candidate.exchange_published_at_utc == wanted_time
    ]
    urls = {candidate.source_url for candidate in rows}
    if len(urls) != 1:
        raise AlphaContractError(
            "T008 same-timestamp filing candidates have ambiguous source URLs"
        )
    return min(rows, key=lambda item: item.source_url)


def select_fundamental_pair(
    payload: object,
    *,
    symbol: str,
    target_period_end: str = TARGET_PERIOD_END,
    baseline_period_end: str = BASELINE_PERIOD_END,
) -> FundamentalPair:
    """Select first target filing and latest already-known same-basis baseline."""

    for basis in BASIS_PREFERENCE:
        target_candidates = _candidate_rows(
            payload,
            symbol=symbol,
            period_end=target_period_end,
            accounting_basis=basis,
        )
        if not target_candidates:
            continue
        target = _unique_at_timestamp(target_candidates, use_first=True)

        baseline_candidates = [
            candidate
            for candidate in _candidate_rows(
                payload,
                symbol=symbol,
                period_end=baseline_period_end,
                accounting_basis=basis,
            )
            if candidate.exchange_published_at_utc
            < target.exchange_published_at_utc
        ]
        if not baseline_candidates:
            continue
        baseline = _unique_at_timestamp(
            baseline_candidates,
            use_first=False,
        )
        return FundamentalPair(
            symbol=symbol.strip().upper(),
            accounting_basis=basis,
            target=target,
            baseline=baseline,
        )
    raise AlphaContractError(
        "T008 no same-basis target/baseline filing pair"
    )


def select_mixed_source_fundamental_pair(
    integrated_payload: object,
    legacy_payload: object,
    *,
    symbol: str,
    target_period_end: str,
    baseline_period_end: str,
) -> FundamentalPair:
    """Select Integrated target plus legacy already-known same-basis baseline."""

    for basis in BASIS_PREFERENCE:
        target_candidates = _candidate_rows(
            integrated_payload,
            symbol=symbol,
            period_end=target_period_end,
            accounting_basis=basis,
        )
        if not target_candidates:
            continue
        target = _unique_at_timestamp(
            target_candidates,
            use_first=True,
        )

        baseline_candidates = [
            candidate
            for candidate in _legacy_candidate_rows(
                legacy_payload,
                symbol=symbol,
                period_end=baseline_period_end,
                accounting_basis=basis,
            )
            if candidate.exchange_published_at_utc
            < target.exchange_published_at_utc
        ]
        if not baseline_candidates:
            continue
        baseline = _unique_at_timestamp(
            baseline_candidates,
            use_first=False,
        )
        return FundamentalPair(
            symbol=symbol.strip().upper(),
            accounting_basis=basis,
            target=target,
            baseline=baseline,
        )

    raise AlphaContractError(
        "T008 D003 no mixed-source same-basis target/baseline filing pair"
    )


def _currency_is_inr(event: FinancialEvent) -> bool:
    value = str(event.currency or "").strip().casefold()
    return value in {
        "inr",
        "indian rupee",
        "indian rupees",
        "rs",
        "rs.",
        "rupee",
        "rupees",
    }


def _html_rounding_scale(rounding: str | None) -> float | None:
    raw = " ".join(str(rounding or "").strip().casefold().split())
    if not raw:
        return None
    if any(token in raw for token in ("crore", "crores")):
        return 10_000_000.0
    if any(token in raw for token in ("lakh", "lakhs", "lac", "lacs")):
        return 100_000.0
    if any(token in raw for token in ("million", "millions")):
        return 1_000_000.0
    if any(token in raw for token in ("thousand", "thousands")):
        return 1_000.0
    if any(
        token in raw
        for token in (
            "actual",
            "actuals",
            "rupee",
            "rupees",
            "unit",
            "units",
        )
    ):
        return 1.0
    return None


def monetary_scale(event: FinancialEvent) -> float:
    if not _currency_is_inr(event):
        raise AlphaContractError(
            f"T008 unsupported presentation currency: {event.currency}"
        )
    if event.parser_version == XBRL_PARSER_VERSION:
        return 1.0
    if event.parser_version == PARSER_VERSION:
        scale = _html_rounding_scale(event.rounding)
        if scale is None:
            raise AlphaContractError(
                f"T008 unsupported HTML rounding metadata: {event.rounding}"
            )
        return scale
    raise AlphaContractError(
        f"T008 unsupported filing parser version: {event.parser_version}"
    )


def normalized_monetary_facts(event: FinancialEvent) -> dict[str, float | None]:
    scale = monetary_scale(event)
    result = {}
    for field in (
        "revenue_from_operations",
        "profit_before_tax",
        "total_profit",
        "exceptional_items",
    ):
        raw = getattr(event, field)
        if raw is None:
            result[field] = None
            continue
        value = float(raw) * scale
        if not math.isfinite(value):
            raise AlphaContractError(
                f"T008 nonfinite normalized financial fact: {field}"
            )
        result[field] = value
    return result


def build_fundamental_features(
    *,
    target_event: FinancialEvent,
    baseline_event: FinancialEvent,
    target_period_end: str = TARGET_PERIOD_END,
    baseline_period_end: str = BASELINE_PERIOD_END,
) -> dict[str, float | None]:
    if target_event.symbol.upper() != baseline_event.symbol.upper():
        raise AlphaContractError("T008 target/baseline symbol mismatch")
    if (
        target_event.accounting_basis.strip().casefold()
        != baseline_event.accounting_basis.strip().casefold()
    ):
        raise AlphaContractError("T008 target/baseline accounting basis mismatch")
    if target_event.reporting_period_end != target_period_end:
        raise AlphaContractError("T008 target event period mismatch")
    if baseline_event.reporting_period_end != baseline_period_end:
        raise AlphaContractError("T008 baseline event period mismatch")

    target = normalized_monetary_facts(target_event)
    baseline = normalized_monetary_facts(baseline_event)
    rev_t = target["revenue_from_operations"]
    rev_b = baseline["revenue_from_operations"]
    pbt_t = target["profit_before_tax"]
    pbt_b = baseline["profit_before_tax"]
    profit_t = target["total_profit"]
    profit_b = baseline["total_profit"]

    def finite_or_none(value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            return None
        return float(value)

    revenue_yoy = None
    pbt_change = None
    profit_change = None
    pbt_margin = None
    pbt_margin_delta = None
    profit_margin_delta = None

    if rev_b is not None and rev_b > 0:
        if rev_t is not None:
            revenue_yoy = rev_t / rev_b - 1.0
        if pbt_t is not None and pbt_b is not None:
            pbt_change = (pbt_t - pbt_b) / abs(rev_b)
        if profit_t is not None and profit_b is not None:
            profit_change = (profit_t - profit_b) / abs(rev_b)

    if rev_t is not None and rev_t > 0:
        if pbt_t is not None:
            pbt_margin = pbt_t / rev_t
        if (
            pbt_t is not None
            and pbt_b is not None
            and rev_b is not None
            and rev_b > 0
        ):
            pbt_margin_delta = pbt_t / rev_t - pbt_b / rev_b
        if (
            profit_t is not None
            and profit_b is not None
            and rev_b is not None
            and rev_b > 0
        ):
            profit_margin_delta = profit_t / rev_t - profit_b / rev_b

    return {
        "revenue_yoy": finite_or_none(revenue_yoy),
        "pbt_change_to_prior_revenue": finite_or_none(pbt_change),
        "total_profit_change_to_prior_revenue": finite_or_none(profit_change),
        "pbt_margin": finite_or_none(pbt_margin),
        "pbt_margin_delta_yoy": finite_or_none(pbt_margin_delta),
        "total_profit_margin_delta_yoy": finite_or_none(
            profit_margin_delta
        ),
    }


def parse_historical_filing(
    raw: bytes,
    *,
    candidate: FilingCandidate,
    raw_path: str,
    captured_at_utc: str,
) -> FinancialEvent:
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AlphaContractError(
            "T008 filing bytes are not UTF-8"
        ) from exc
    event = parse_indas_document(
        document,
        source_url=candidate.source_url,
        raw_sha256=sha256_bytes(raw),
        raw_path=raw_path,
        captured_at_utc=captured_at_utc,
        mode=HISTORICAL_RECONSTRUCTION,
    )
    if event.symbol.upper() != candidate.symbol.upper():
        raise AlphaContractError("T008 parsed filing symbol mismatch")
    if event.reporting_period_end != candidate.period_end:
        raise AlphaContractError("T008 parsed filing period mismatch")
    if (
        event.accounting_basis.strip().casefold()
        != candidate.accounting_basis.strip().casefold()
    ):
        raise AlphaContractError("T008 parsed filing basis mismatch")
    return event


def pair_record(
    *,
    pair: FundamentalPair,
    target_event: FinancialEvent,
    baseline_event: FinancialEvent,
    discovery_raw_sha256: str,
    diagnostic_id: str = T008_D001_ID,
) -> dict[str, Any]:
    features = build_fundamental_features(
        target_event=target_event,
        baseline_event=baseline_event,
        target_period_end=pair.target.period_end,
        baseline_period_end=pair.baseline.period_end,
    )
    complete_count = sum(value is not None for value in features.values())
    exceptional_ratio = None
    target_facts = normalized_monetary_facts(target_event)
    if (
        target_facts["exceptional_items"] is not None
        and target_facts["revenue_from_operations"] is not None
        and target_facts["revenue_from_operations"] > 0
    ):
        exceptional_ratio = (
            target_facts["exceptional_items"]
            / target_facts["revenue_from_operations"]
        )
    record: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": diagnostic_id,
        "symbol": pair.symbol,
        "target_period_end": pair.target.period_end,
        "baseline_period_end": pair.baseline.period_end,
        "accounting_basis": pair.accounting_basis,
        "target_exchange_published_at_utc": (
            pair.target.exchange_published_at_utc
        ),
        "baseline_exchange_published_at_utc": (
            pair.baseline.exchange_published_at_utc
        ),
        "target_source_url": pair.target.source_url,
        "baseline_source_url": pair.baseline.source_url,
        "target_discovery_row_sha256": pair.target.discovery_row_sha256,
        "baseline_discovery_row_sha256": pair.baseline.discovery_row_sha256,
        "discovery_raw_sha256": discovery_raw_sha256,
        "target_raw_sha256": target_event.provenance.raw_sha256,
        "baseline_raw_sha256": baseline_event.provenance.raw_sha256,
        "target_parser_version": target_event.parser_version,
        "baseline_parser_version": baseline_event.parser_version,
        "target_currency": target_event.currency,
        "baseline_currency": baseline_event.currency,
        "target_rounding": target_event.rounding,
        "baseline_rounding": baseline_event.rounding,
        "features": features,
        "complete_feature_count": complete_count,
        "all_six_features_complete": complete_count == len(FEATURE_NAMES),
        "exceptional_items_to_revenue_diagnostic": exceptional_ratio,
        "return_outcomes_opened": False,
        "live_capital_allowed": False,
    }
    record["record_sha256"] = digest(record)
    return record
