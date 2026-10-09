from __future__ import annotations

import math
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

CENSUS_ID = "HA001-D001-v1"
SOURCE_PANEL_ID = "FA001-D002-v1"
SOURCE_PANEL_SHA256 = "cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
SOURCE_CENSUS_SHA256 = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EXPECTED_COUNT = 2319
EXPECTED_PERIOD = "2026-03-31"

FLAG_FIELDS: dict[str, tuple[str, ...]] = {
    "MATERIAL_FINANCIAL_SURPLUS_PROXY": (
        "cash",
        "current_investments",
        "borrowings_current",
        "borrowings_noncurrent",
        "total_assets",
    ),
    "MATERIAL_BOOK_INVESTMENTS": (
        "current_investments",
        "noncurrent_investments",
        "total_assets",
    ),
    "TANGIBLE_CAPITAL_CONCENTRATION": (
        "ppe",
        "capital_work_in_progress",
        "investment_property",
        "total_assets",
    ),
}

THRESHOLDS = {
    "MATERIAL_FINANCIAL_SURPLUS_PROXY": 0.20,
    "MATERIAL_BOOK_INVESTMENTS": 0.30,
    "TANGIBLE_CAPITAL_CONCENTRATION": 0.50,
}

STATES = frozenset(
    {
        "FLAGGED",
        "NOT_FLAGGED",
        "MISSING_REQUIRED_FACT",
        "INVALID_NUMERIC_OR_UNIT",
        "FINANCIAL_SECTOR_NOT_COMPARABLE",
        "ANNUAL_SOURCE_UNAVAILABLE",
    }
)

NONNEGATIVE_FIELDS = frozenset(
    {
        "cash",
        "current_investments",
        "noncurrent_investments",
        "borrowings_current",
        "borrowings_noncurrent",
        "ppe",
        "capital_work_in_progress",
        "investment_property",
    }
)


def _source_is_nbfc(source_url: str) -> bool:
    # Source taxonomy is explicit in the exchange filename; this is not an
    # inference about the issuer's industry or future business performance.
    return "INTEGRATED_FILING_NBFC_" in urlparse(source_url).path.upper()


def _source_facts(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    annual = row.get("annual")
    if not isinstance(annual, dict) or annual.get("status") != "READY":
        return "ANNUAL_SOURCE_UNAVAILABLE", None

    parsed = annual.get("parsed")
    if not isinstance(parsed, dict):
        return "ANNUAL_SOURCE_UNAVAILABLE", None
    if parsed.get("period_end") != EXPECTED_PERIOD:
        return "ANNUAL_SOURCE_UNAVAILABLE", None

    source_url = parsed.get("source_url")
    sha = parsed.get("raw_sha256")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        return "ANNUAL_SOURCE_UNAVAILABLE", None
    if not isinstance(sha, str) or len(sha) != 64:
        return "ANNUAL_SOURCE_UNAVAILABLE", None

    if _source_is_nbfc(source_url):
        return "FINANCIAL_SECTOR_NOT_COMPARABLE", parsed
    facts = parsed.get("facts")
    if not isinstance(facts, dict):
        return "ANNUAL_SOURCE_UNAVAILABLE", None
    return "READY", parsed


def _evaluate_flag(
    flag: str, source_state: str, parsed: dict[str, Any] | None
) -> dict[str, Any]:
    required = FLAG_FIELDS[flag]
    if source_state != "READY" or parsed is None:
        return {
            "state": source_state,
            "ratio": None,
            "numerator_inr": None,
            "total_assets_inr": None,
            "evidence": {},
        }

    facts = parsed["facts"]
    evidence: dict[str, dict[str, Any]] = {}
    missing = False
    invalid = False
    values: dict[str, float] = {}

    for field in required:
        fact = facts.get(field)
        if not isinstance(fact, dict) or fact.get("status") != "READY":
            missing = True
            continue

        raw = fact.get("value")
        unit = fact.get("unit_ref")
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (float, int))
            or not math.isfinite(float(raw))
            or unit != "INR"
        ):
            invalid = True
            continue
        value = float(raw)
        if (field in NONNEGATIVE_FIELDS and value < 0) or (
            field == "total_assets" and value <= 0
        ):
            invalid = True
            continue

        context_refs = fact.get("context_refs")
        concept = fact.get("selected_concept")
        if not isinstance(concept, str) or not concept or not isinstance(
            context_refs, list
        ) or not context_refs or not all(
            isinstance(context, str) and context for context in context_refs
        ):
            invalid = True
            continue

        values[field] = value
        evidence[field] = {
            "value": value,
            "unit_ref": unit,
            "selected_concept": concept,
            "context_refs": sorted(context_refs),
        }

    if invalid:
        state = "INVALID_NUMERIC_OR_UNIT"
    elif missing:
        state = "MISSING_REQUIRED_FACT"
    else:
        state = "READY"

    if state != "READY":
        return {
            "state": state,
            "ratio": None,
            "numerator_inr": None,
            "total_assets_inr": None,
            "evidence": evidence,
        }

    if flag == "MATERIAL_FINANCIAL_SURPLUS_PROXY":
        numerator = (
            values["cash"]
            + values["current_investments"]
            - values["borrowings_current"]
            - values["borrowings_noncurrent"]
        )
    elif flag == "MATERIAL_BOOK_INVESTMENTS":
        numerator = values["current_investments"] + values["noncurrent_investments"]
    elif flag == "TANGIBLE_CAPITAL_CONCENTRATION":
        numerator = (
            values["ppe"]
            + values["capital_work_in_progress"]
            + values["investment_property"]
        )
    else:
        raise AlphaContractError(f"HA001 unknown signal: {flag}")

    assets = values["total_assets"]
    ratio = numerator / assets
    if not math.isfinite(ratio):
        raise AlphaContractError(f"HA001 nonfinite ratio: {flag}")

    return {
        "state": "FLAGGED" if ratio >= THRESHOLDS[flag] else "NOT_FLAGGED",
        "ratio": ratio,
        "numerator_inr": numerator,
        "total_assets_inr": assets,
        "evidence": evidence,
    }


def build_asset_anomaly_census(panel: dict[str, Any]) -> dict[str, Any]:
    if panel.get("panel_id") != SOURCE_PANEL_ID:
        raise AlphaContractError("HA001 requires FA001-D002 source")
    if panel.get("panel_sha256") != SOURCE_PANEL_SHA256:
        raise AlphaContractError("HA001 source panel SHA mismatch")
    if panel.get("source_ss001_census_sha256") != SOURCE_CENSUS_SHA256:
        raise AlphaContractError("HA001 SS001 source census SHA mismatch")
    if panel.get("identity_count") != EXPECTED_COUNT:
        raise AlphaContractError("HA001 source population mismatch")
    if panel.get("feasibility_pass") is not True:
        raise AlphaContractError("HA001 requires passed FA001 source coverage")
    for key in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if panel.get(key) is not False:
            raise AlphaContractError(f"HA001 source requires {key}=false")

    source_rows = panel.get("rows")
    if not isinstance(source_rows, list) or len(source_rows) != EXPECTED_COUNT:
        raise AlphaContractError("HA001 source rows are incomplete")

    seen_symbols: set[str] = set()
    output_rows = []
    state_counts: dict[str, Counter[str]] = {
        flag: Counter() for flag in FLAG_FIELDS
    }
    flagged_symbols: dict[str, list[str]] = {flag: [] for flag in FLAG_FIELDS}

    for row in source_rows:
        if not isinstance(row, dict):
            raise TypeError("HA001 source row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in seen_symbols:
            raise AlphaContractError("HA001 source symbol is missing or duplicated")
        seen_symbols.add(symbol)

        source_state, parsed = _source_facts(row)
        flags = {}
        for flag in FLAG_FIELDS:
            result = _evaluate_flag(flag, source_state, parsed)
            if result["state"] not in STATES:
                raise AlphaContractError("HA001 emitted unknown signal state")
            state_counts[flag][result["state"]] += 1
            if result["state"] == "FLAGGED":
                flagged_symbols[flag].append(symbol)
            flags[flag] = result

        annual = row.get("annual")
        annual_status = annual.get("status") if isinstance(annual, dict) else None
        record = {
            "symbol": symbol,
            "isin": row.get("isin"),
            "company_name": row.get("company_name"),
            "in_existing_u001": row.get("in_existing_u001"),
            "annual_source_status": annual_status,
            "annual_accounting_basis": (
                parsed.get("accounting_basis") if parsed else None
            ),
            "annual_period_end": parsed.get("period_end") if parsed else None,
            "annual_source_url": parsed.get("source_url") if parsed else None,
            "annual_raw_sha256": parsed.get("raw_sha256") if parsed else None,
            "signals": flags,
            "return_outcomes_opened": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        output_rows.append(record)

    output_rows.sort(key=lambda row: row["symbol"])
    result = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "ANNUAL_BALANCE_SHEET_ASSET_TRIAGE_NOT_VALUATION",
        "input_source_panel_sha256": SOURCE_PANEL_SHA256,
        "input_ss001_census_sha256": SOURCE_CENSUS_SHA256,
        "source_period_end": EXPECTED_PERIOD,
        "identity_count": EXPECTED_COUNT,
        "signal_thresholds": THRESHOLDS,
        "signal_state_counts": {
            flag: dict(sorted(counts.items()))
            for flag, counts in sorted(state_counts.items())
        },
        "flagged_symbol_lists": {
            flag: sorted(symbols) for flag, symbols in sorted(flagged_symbols.items())
        },
        "any_signal_flagged_count": sum(
            any(signal["state"] == "FLAGGED" for signal in row["signals"].values())
            for row in output_rows
        ),
        "rows": output_rows,
        "source_only_gate_pass": True,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "market_capitalization_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["census_sha256"] = digest(result)
    return result
