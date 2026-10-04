from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.fa001_schema_audit import (
    ANNUAL_ALIASES,
    ANNUAL_PERIOD_END,
    QUARTER_ALIASES,
    QUARTER_PERIOD_END,
    FilingCandidate,
)

PANEL_ID = "FA001-D002-v1"
EXPECTED_SS001_CENSUS_ID = "SS001-D001-v1"
EXPECTED_SS001_CENSUS_SHA = (
    "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
)
EXPECTED_IDENTITY_COUNT = 2319
SHARD_COUNT = 6


class FA001FactError(ValueError):
    """Raised when a frozen FA001 fact cannot be resolved without guessing."""


@dataclass(frozen=True)
class Context:
    context_id: str
    start_date: str | None
    end_date: str | None
    instant: str | None
    dimensional: bool


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _parse_iso_date(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def _numeric(value: object) -> float | None:
    raw = _clean(value).replace(",", "").replace("₹", "")
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


def _contexts(root: ET.Element) -> dict[str, Context]:
    result: dict[str, Context] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        start = None
        end = None
        instant = None
        dimensional = False
        for child in element.iter():
            name = _local_name(child.tag)
            if name == "startDate":
                start = _parse_iso_date(child.text)
            elif name == "endDate":
                end = _parse_iso_date(child.text)
            elif name == "instant":
                instant = _parse_iso_date(child.text)
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        result[context_id] = Context(
            context_id=context_id,
            start_date=start,
            end_date=end,
            instant=instant,
            dimensional=dimensional,
        )
    return result


def deterministic_shard(symbol: str, *, shard_count: int = SHARD_COUNT) -> int:
    if shard_count <= 0:
        raise ValueError("FA001 shard_count must be positive")
    wanted = symbol.strip().upper()
    if not wanted:
        raise ValueError("FA001 shard symbol is required")
    value = int(hashlib.sha256(wanted.encode("utf-8")).hexdigest(), 16)
    return value % shard_count


def _fact_rows(
    root: ET.Element,
    contexts: dict[str, Context],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        concept = _local_name(element.tag)
        numeric = _numeric(element.text)
        if numeric is None:
            continue
        context = contexts.get(context_ref)
        if context is None:
            continue
        result.setdefault(concept, []).append(
            {
                "context_ref": context_ref,
                "value": numeric,
                "unit_ref": element.attrib.get("unitRef"),
                "start_date": context.start_date,
                "end_date": context.end_date,
                "instant": context.instant,
                "dimensional": context.dimensional,
            }
        )
    return result


def _context_ids(
    contexts: dict[str, Context],
    *,
    period_end: str,
    duration_min_days: int | None,
    duration_max_days: int | None,
    instant: bool,
) -> set[str]:
    result = set()
    end = date.fromisoformat(period_end)
    for context_id, context in contexts.items():
        if context.dimensional:
            continue
        if instant:
            if context.instant == period_end:
                result.add(context_id)
            continue
        if context.start_date is None or context.end_date != period_end:
            continue
        days = (end - date.fromisoformat(context.start_date)).days + 1
        if (
            duration_min_days is not None
            and duration_max_days is not None
            and duration_min_days <= days <= duration_max_days
        ):
            result.add(context_id)
    return result


def _resolve_family(
    facts: dict[str, list[dict[str, Any]]],
    *,
    aliases: tuple[str, ...],
    allowed_context_ids: set[str],
) -> dict[str, Any]:
    for alias in aliases:
        rows = [
            row
            for row in facts.get(alias, [])
            if row["context_ref"] in allowed_context_ids
        ]
        if not rows:
            continue
        values = {float(row["value"]) for row in rows}
        units = {
            str(row["unit_ref"])
            for row in rows
            if row.get("unit_ref") not in (None, "")
        }
        if len(values) != 1 or len(units) > 1:
            return {
                "status": "AMBIGUOUS",
                "value": None,
                "selected_concept": alias,
                "unit_ref": None,
                "matching_fact_count": len(rows),
                "context_refs": sorted({str(row["context_ref"]) for row in rows}),
            }
        return {
            "status": "READY",
            "value": next(iter(values)),
            "selected_concept": alias,
            "unit_ref": next(iter(units)) if units else None,
            "matching_fact_count": len(rows),
            "context_refs": sorted({str(row["context_ref"]) for row in rows}),
        }
    return {
        "status": "MISSING",
        "value": None,
        "selected_concept": None,
        "unit_ref": None,
        "matching_fact_count": 0,
        "context_refs": [],
    }


def parse_filing_facts(
    raw: bytes,
    *,
    candidate: FilingCandidate,
    filing_kind: str,
) -> dict[str, Any]:
    if filing_kind not in {"ANNUAL", "QUARTER"}:
        raise ValueError("FA001 filing_kind must be ANNUAL or QUARTER")
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FA001FactError("XBRL is not UTF-8") from exc
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise FA001FactError(f"XBRL is not well formed: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise FA001FactError("source root is not XBRL")

    contexts = _contexts(root)
    fact_rows = _fact_rows(root, contexts)

    symbol_values = {
        _clean(element.text).upper()
        for element in root.iter()
        if _local_name(element.tag).casefold() == "symbol"
        and _clean(element.text)
    }
    if symbol_values and candidate.symbol not in symbol_values:
        raise FA001FactError(
            f"filing symbol mismatch: expected {candidate.symbol}, observed {sorted(symbol_values)}"
        )

    if filing_kind == "ANNUAL":
        if candidate.period_end != ANNUAL_PERIOD_END:
            raise FA001FactError("annual candidate period differs from frozen endpoint")
        instant_ids = _context_ids(
            contexts,
            period_end=candidate.period_end,
            duration_min_days=None,
            duration_max_days=None,
            instant=True,
        )
        duration_ids = _context_ids(
            contexts,
            period_end=candidate.period_end,
            duration_min_days=350,
            duration_max_days=380,
            instant=False,
        )
        duration_families = {
            "basic_eps",
            "operating_cash_flow",
            "purchase_ppe",
            "sale_ppe",
            "purchase_investments",
            "sale_investments",
        }
        facts = {
            family: _resolve_family(
                fact_rows,
                aliases=aliases,
                allowed_context_ids=(
                    duration_ids if family in duration_families else instant_ids
                ),
            )
            for family, aliases in ANNUAL_ALIASES.items()
        }
        context_summary = {
            "year_end_instant_context_count": len(instant_ids),
            "annual_duration_context_count": len(duration_ids),
        }
    else:
        if candidate.period_end != QUARTER_PERIOD_END:
            raise FA001FactError("quarter candidate period differs from frozen endpoint")
        quarter_ids = _context_ids(
            contexts,
            period_end=candidate.period_end,
            duration_min_days=80,
            duration_max_days=100,
            instant=False,
        )
        facts = {
            family: _resolve_family(
                fact_rows,
                aliases=aliases,
                allowed_context_ids=quarter_ids,
            )
            for family, aliases in QUARTER_ALIASES.items()
        }
        context_summary = {
            "quarter_duration_context_count": len(quarter_ids),
        }

    return {
        "filing_kind": filing_kind,
        "symbol": candidate.symbol,
        "accounting_basis": candidate.accounting_basis,
        "period_end": candidate.period_end,
        "exchange_published_at_utc": candidate.exchange_published_at_utc,
        "source_url": candidate.source_url,
        "discovery_row_sha256": candidate.discovery_row_sha256,
        "raw_sha256": sha256_bytes(raw),
        "context_summary": context_summary,
        "facts": facts,
    }


def validate_d001_census(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_SS001_CENSUS_ID:
        raise AlphaContractError("FA001 D002 requires frozen SS001-D001 census")
    if census.get("census_sha256") != EXPECTED_SS001_CENSUS_SHA:
        raise AlphaContractError("FA001 D002 SS001 census SHA mismatch")
    if census.get("eq_identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("FA001 D002 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"FA001 D002 requires SS001 {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("FA001 D002 SS001 rows unavailable")
    return rows


def build_full_fact_panel(
    *,
    d001_census: dict[str, Any],
    shard_payloads: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    source_rows = validate_d001_census(d001_census)
    expected = {
        str(row["symbol"]).upper(): row
        for row in source_rows
        if isinstance(row, dict)
    }
    if len(expected) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("FA001 D002 frozen symbols are not unique")

    shard_indexes = {
        int(payload.get("shard_index"))
        for payload in shard_payloads
        if isinstance(payload, dict)
    }
    if shard_indexes != set(range(SHARD_COUNT)):
        raise AlphaContractError("FA001 D002 shard set is incomplete")

    merged: dict[str, dict[str, Any]] = {}
    for payload in shard_payloads:
        if payload.get("shard_count") != SHARD_COUNT:
            raise AlphaContractError("FA001 D002 shard_count mismatch")
        if payload.get("source_census_sha256") != EXPECTED_SS001_CENSUS_SHA:
            raise AlphaContractError("FA001 D002 shard census SHA mismatch")
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise TypeError("FA001 D002 shard rows must be a list")
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("FA001 D002 fact rows must be objects")
            symbol = str(row.get("symbol") or "").upper()
            if symbol not in expected or symbol in merged:
                raise AlphaContractError("FA001 D002 merged identity mismatch")
            expected_shard = deterministic_shard(symbol)
            if expected_shard != int(payload["shard_index"]):
                raise AlphaContractError(f"{symbol}: wrong deterministic shard")
            if row.get("isin") != expected[symbol].get("isin"):
                raise AlphaContractError(f"{symbol}: frozen ISIN mismatch")
            merged[symbol] = row
    if set(merged) != set(expected):
        raise AlphaContractError("FA001 D002 merged rows do not cover frozen universe")

    annual_source_count = 0
    quarter_source_count = 0
    annual_core_count = 0
    borrowing_count = 0
    investment_count = 0
    quarter_revenue_pat_count = 0
    annual_state_counts: Counter[str] = Counter()
    quarter_state_counts: Counter[str] = Counter()
    fact_ready_counts: Counter[str] = Counter()
    integrity_ok = True

    for row in merged.values():
        annual = row.get("annual")
        quarter = row.get("quarter")
        if not isinstance(annual, dict) or not isinstance(quarter, dict):
            raise AlphaContractError("FA001 D002 row source states unavailable")
        annual_state = str(annual.get("status"))
        quarter_state = str(quarter.get("status"))
        annual_state_counts[annual_state] += 1
        quarter_state_counts[quarter_state] += 1

        if annual.get("candidate") is not None:
            annual_source_count += 1
        if quarter.get("candidate") is not None:
            quarter_source_count += 1

        if annual_state == "READY":
            parsed = annual.get("parsed")
            if not isinstance(parsed, dict) or not parsed.get("raw_sha256"):
                integrity_ok = False
                continue
            facts = parsed.get("facts")
            if not isinstance(facts, dict):
                integrity_ok = False
                continue
            for family, fact in facts.items():
                if isinstance(fact, dict) and fact.get("status") == "READY":
                    fact_ready_counts[f"annual.{family}"] += 1
            if all(
                isinstance(facts.get(name), dict)
                and facts[name].get("status") == "READY"
                for name in ("total_assets", "total_equity", "cash")
            ):
                annual_core_count += 1
            if all(
                isinstance(facts.get(name), dict)
                and facts[name].get("status") == "READY"
                for name in ("borrowings_current", "borrowings_noncurrent")
            ):
                borrowing_count += 1
            if any(
                isinstance(facts.get(name), dict)
                and facts[name].get("status") == "READY"
                for name in ("current_investments", "noncurrent_investments")
            ):
                investment_count += 1

        if quarter_state == "READY":
            parsed = quarter.get("parsed")
            if not isinstance(parsed, dict) or not parsed.get("raw_sha256"):
                integrity_ok = False
                continue
            facts = parsed.get("facts")
            if not isinstance(facts, dict):
                integrity_ok = False
                continue
            for family, fact in facts.items():
                if isinstance(fact, dict) and fact.get("status") == "READY":
                    fact_ready_counts[f"quarter.{family}"] += 1
            if all(
                isinstance(facts.get(name), dict)
                and facts[name].get("status") == "READY"
                for name in ("revenue", "pat")
            ):
                quarter_revenue_pat_count += 1

    n = EXPECTED_IDENTITY_COUNT
    gates = {
        "complete_identity_accounting": len(merged) == n,
        "minimum_annual_source_75pct": annual_source_count / n >= 0.75,
        "minimum_quarter_source_80pct": quarter_source_count / n >= 0.80,
        "minimum_annual_core_assets_65pct": annual_core_count / n >= 0.65,
        "minimum_borrowings_60pct": borrowing_count / n >= 0.60,
        "minimum_investments_60pct": investment_count / n >= 0.60,
        "minimum_quarter_revenue_pat_70pct": quarter_revenue_pat_count / n >= 0.70,
        "ready_filing_source_integrity": integrity_ok,
    }

    output = {
        "schema_version": 1,
        "panel_id": PANEL_ID,
        "classification": "FULL_MARKET_FINANCIAL_ASSET_FACT_PLANE_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_ss001_census_sha256": EXPECTED_SS001_CENSUS_SHA,
        "identity_count": n,
        "annual_source_count": annual_source_count,
        "annual_source_ratio": annual_source_count / n,
        "quarter_source_count": quarter_source_count,
        "quarter_source_ratio": quarter_source_count / n,
        "annual_core_assets_ready_count": annual_core_count,
        "annual_core_assets_ready_ratio": annual_core_count / n,
        "borrowings_ready_count": borrowing_count,
        "borrowings_ready_ratio": borrowing_count / n,
        "investments_ready_count": investment_count,
        "investments_ready_ratio": investment_count / n,
        "quarter_revenue_pat_ready_count": quarter_revenue_pat_count,
        "quarter_revenue_pat_ready_ratio": quarter_revenue_pat_count / n,
        "annual_source_state_counts": dict(sorted(annual_state_counts.items())),
        "quarter_source_state_counts": dict(sorted(quarter_state_counts.items())),
        "fact_ready_counts": dict(sorted(fact_ready_counts.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_hidden_asset_and_inflection_design": all(gates.values()),
        "rows": [merged[symbol] for symbol in sorted(merged)],
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["panel_sha256"] = digest(output)
    return output
