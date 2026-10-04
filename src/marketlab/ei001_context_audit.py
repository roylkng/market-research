from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.fa001_schema_audit import FilingCandidate, QUARTER_ALIASES

AUDIT_ID = "EI001-D001-v1"
CURRENT_END = "2026-06-30"
PRIOR_END = "2025-06-30"

AUDIT_FAMILIES = (
    "revenue",
    "pat",
    "pbt",
    "finance_costs",
    "depreciation",
    "basic_eps",
)


class EI001ContextError(ValueError):
    """Raised when comparative-quarter XBRL semantics are ambiguous."""


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_date(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


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


def _duration_contexts(
    root: ET.Element,
    *,
    end_date: str,
) -> set[str]:
    wanted_end = date.fromisoformat(end_date)
    result: set[str] = set()
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        start = None
        end = None
        dimensional = False
        for child in element.iter():
            name = _local_name(child.tag)
            if name == "startDate":
                start = _parse_date(child.text)
            elif name == "endDate":
                end = _parse_date(child.text)
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        if dimensional or start is None or end != end_date:
            continue
        days = (wanted_end - date.fromisoformat(start)).days + 1
        if 80 <= days <= 100:
            result.add(context_id)
    return result


def _facts(root: ET.Element) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        value = _numeric(element.text)
        if value is None:
            continue
        name = _local_name(element.tag)
        result.setdefault(name, []).append(
            {
                "context_ref": context_ref,
                "value": value,
                "unit_ref": element.attrib.get("unitRef"),
            }
        )
    return result


def _family_state(
    facts: dict[str, list[dict[str, Any]]],
    *,
    aliases: tuple[str, ...],
    context_ids: set[str],
) -> dict[str, Any]:
    for alias in aliases:
        rows = [
            row
            for row in facts.get(alias, [])
            if row["context_ref"] in context_ids
        ]
        if not rows:
            continue
        values = {float(row["value"]) for row in rows}
        units = {str(row.get("unit_ref") or "") for row in rows}
        context_refs = sorted({str(row["context_ref"]) for row in rows})
        if len(values) != 1:
            return {
                "status": "AMBIGUOUS_VALUE",
                "selected_concept": alias,
                "value": None,
                "unit_ref": None,
                "context_refs": context_refs,
            }
        if len(units) != 1 or "" in units:
            return {
                "status": "AMBIGUOUS_OR_MISSING_UNIT",
                "selected_concept": alias,
                "value": next(iter(values)),
                "unit_ref": None,
                "context_refs": context_refs,
            }
        return {
            "status": "READY",
            "selected_concept": alias,
            "value": next(iter(values)),
            "unit_ref": next(iter(units)),
            "context_refs": context_refs,
        }
    return {
        "status": "MISSING",
        "selected_concept": None,
        "value": None,
        "unit_ref": None,
        "context_refs": [],
    }


def parse_comparative_quarter(
    raw: bytes,
    *,
    candidate: FilingCandidate,
) -> dict[str, Any]:
    if candidate.period_end != CURRENT_END:
        raise EI001ContextError("EI001 D001 requires 2026-06-30 filing candidate")
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EI001ContextError("EI001 XBRL is not UTF-8") from exc
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise EI001ContextError(f"EI001 XBRL is not well formed: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise EI001ContextError("EI001 source root is not XBRL")

    current_contexts = _duration_contexts(root, end_date=CURRENT_END)
    prior_contexts = _duration_contexts(root, end_date=PRIOR_END)
    facts = _facts(root)

    periods: dict[str, dict[str, Any]] = {"current": {}, "prior_year": {}}
    comparable: dict[str, dict[str, Any]] = {}
    for family in AUDIT_FAMILIES:
        aliases = QUARTER_ALIASES[family]
        current = _family_state(facts, aliases=aliases, context_ids=current_contexts)
        prior = _family_state(facts, aliases=aliases, context_ids=prior_contexts)
        periods["current"][family] = current
        periods["prior_year"][family] = prior
        ready = (
            current["status"] == "READY"
            and prior["status"] == "READY"
            and current["unit_ref"] == prior["unit_ref"]
        )
        comparable[family] = {
            "status": "COMPARABLE_READY" if ready else "NOT_COMPARABLE",
            "unit_match": (
                current.get("unit_ref") is not None
                and current.get("unit_ref") == prior.get("unit_ref")
            ),
        }

    return {
        "symbol": candidate.symbol,
        "accounting_basis": candidate.accounting_basis,
        "period_end": candidate.period_end,
        "source_url": candidate.source_url,
        "exchange_published_at_utc": candidate.exchange_published_at_utc,
        "raw_sha256": sha256_bytes(raw),
        "current_context_count": len(current_contexts),
        "prior_year_context_count": len(prior_contexts),
        "periods": periods,
        "comparable": comparable,
    }


def build_context_audit(
    *,
    sample: dict[str, Any],
    observations: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    sample_rows = sample.get("symbols")
    if not isinstance(sample_rows, list) or len(sample_rows) != 48:
        raise AlphaContractError("EI001 D001 requires frozen 48-symbol sample")
    expected = {str(row.get("symbol") or "").upper() for row in sample_rows}
    if len(expected) != 48:
        raise AlphaContractError("EI001 D001 sample symbols must be unique")

    by_symbol: dict[str, dict[str, Any]] = {}
    for row in observations:
        if not isinstance(row, dict):
            raise TypeError("EI001 D001 observations must be objects")
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in expected or symbol in by_symbol:
            raise AlphaContractError("EI001 D001 observation identity mismatch")
        by_symbol[symbol] = row
    if set(by_symbol) != expected:
        raise AlphaContractError("EI001 D001 observations do not cover frozen sample")

    usable = 0
    family_ready: Counter[str] = Counter()
    revenue_pat = 0
    revenue_pat_pbt = 0
    states: Counter[str] = Counter()

    for symbol in sorted(expected):
        row = by_symbol[symbol]
        if row.get("status") != "READY":
            states[str(row.get("reason") or "UNAVAILABLE")] += 1
            continue
        usable += 1
        parsed = row.get("parsed")
        if not isinstance(parsed, dict):
            raise AlphaContractError(f"{symbol}: READY observation lacks parsed payload")
        comparable = parsed.get("comparable")
        if not isinstance(comparable, dict):
            raise AlphaContractError(f"{symbol}: comparable map unavailable")
        ready_set = {
            family
            for family in AUDIT_FAMILIES
            if isinstance(comparable.get(family), dict)
            and comparable[family].get("status") == "COMPARABLE_READY"
        }
        for family in ready_set:
            family_ready[family] += 1
        if {"revenue", "pat"}.issubset(ready_set):
            revenue_pat += 1
        if {"revenue", "pat", "pbt"}.issubset(ready_set):
            revenue_pat_pbt += 1

    denom = max(usable, 1)
    gates = {
        "minimum_usable_current_xbrl_40_of_48": usable >= 40,
        "comparable_revenue_75pct": family_ready["revenue"] / denom >= 0.75,
        "comparable_pat_75pct": family_ready["pat"] / denom >= 0.75,
        "comparable_revenue_pat_70pct": revenue_pat / denom >= 0.70,
        "comparable_revenue_pat_pbt_60pct": revenue_pat_pbt / denom >= 0.60,
    }
    output = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "COMPARATIVE_QUARTER_XBRL_CONTEXT_AUDIT_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "sample_count": 48,
        "sample_sha256": digest(sample),
        "usable_current_xbrl_count": usable,
        "comparable_family_counts": dict(sorted(family_ready.items())),
        "comparable_revenue_pat_count": revenue_pat,
        "comparable_revenue_pat_pbt_count": revenue_pat_pbt,
        "source_state_counts": dict(sorted(states.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_full_market_comparative_plane": all(gates.values()),
        "observations": sorted(observations, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["audit_sha256"] = digest(output)
    return output
