from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

PANEL_ID = "GF001-D002-v1"
EXPECTED_D002_ID = "SS001-D002-v1"
EXPECTED_D002_SHA = "214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293"
EXPECTED_IDENTITY_COUNT = 2319
EXPECTED_READY_LATEST = 2050
EXPECTED_ADJACENT = 2032

SHARE_PCT_CONCEPT = "ShareholdingAsAPercentageOfTotalNumberOfShares"

AGGREGATE_CONTEXTS = {
    "PROMOTER_GROUP": (
        "ShareholdingOfPromoterAndPromoterGroup_ContextI",
        "ShareholdingOfPromoterAndPromoterGroupMember",
    ),
    "PUBLIC": (
        "PublicShareholding_ContextI",
        "PublicShareholdingMember",
    ),
    "MUTUAL_FUND_UTI": (
        "MutualFundsOrUTI_ContextI",
        "MutualFundsOrUTIMember",
    ),
}

ENCUMBRANCE_CONCEPTS = {
    "pledge": (
        "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledged"
        "ForPromoterAndPromoterGroup"
    ),
    "non_disposal_undertaking": (
        "WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertaking"
        "ForPromoterAndPromoterGroup"
    ),
    "other_encumbrance": (
        "WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDU"
        "ForPromoterAndPromoterGroup"
    ),
}


class GF001GovernanceError(ValueError):
    """Raised when current governance XBRL cannot be parsed without guessing."""


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _qname_local(value: object) -> str:
    raw = str(value or "").strip()
    return raw.rsplit(":", 1)[-1] if raw else ""


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _number(value: object) -> float | None:
    raw = _clean(value).replace(",", "")
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _contexts(root: ET.Element) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = str(element.attrib.get("id") or "").strip()
        if not context_id:
            continue
        if context_id in result:
            raise GF001GovernanceError(f"duplicate XBRL context id: {context_id}")
        members: list[tuple[str, str]] = []
        typed = False
        instant = None
        for child in element.iter():
            local = _local_name(child.tag)
            if local == "explicitMember":
                members.append(
                    (
                        _qname_local(child.attrib.get("dimension")),
                        _qname_local(child.text),
                    )
                )
            elif local == "typedMember":
                typed = True
            elif local == "instant":
                instant = _clean(child.text) or None
        result[context_id] = {
            "explicit_members": tuple(sorted(members)),
            "has_typed_member": typed,
            "instant": instant,
        }
    return result


def _fact_rows(root: ET.Element) -> list[dict[str, Any]]:
    rows = []
    for element in root.iter():
        context_ref = str(
            element.attrib.get("contextRef")
            or element.attrib.get("contextref")
            or ""
        ).strip()
        if not context_ref:
            continue
        rows.append(
            {
                "concept": _local_name(element.tag),
                "context_ref": context_ref,
                "raw_value": _clean(element.text),
                "numeric_value": _number(element.text),
            }
        )
    return rows


def _exact_aggregate(
    contexts: dict[str, dict[str, Any]],
    facts: list[dict[str, Any]],
    *,
    family: str,
) -> tuple[str, float | None]:
    context_id, member = AGGREGATE_CONTEXTS[family]
    context = contexts.get(context_id)
    if context is None:
        return "CATEGORY_CONTEXT_ABSENT", None
    if context["has_typed_member"]:
        return "AMBIGUOUS_OR_INVALID", None
    expected_members = (("CategoryOfShareholdersAxis", member),)
    if context["explicit_members"] != expected_members:
        return "AMBIGUOUS_OR_INVALID", None

    matches = [
        row
        for row in facts
        if row["concept"] == SHARE_PCT_CONCEPT
        and row["context_ref"] == context_id
    ]
    if len(matches) != 1:
        return "AMBIGUOUS_OR_INVALID", None
    value = matches[0]["numeric_value"]
    if value is None or not 0.0 <= float(value) <= 1.0:
        return "AMBIGUOUS_OR_INVALID", None
    return "READY", float(value)


def _exact_boolean(
    facts: list[dict[str, Any]],
    *,
    concept: str,
) -> bool | None:
    matches = [
        row
        for row in facts
        if row["concept"] == concept and row["context_ref"] == "MainI"
    ]
    if len(matches) != 1:
        return None
    raw = str(matches[0]["raw_value"]).strip().casefold()
    if raw == "true":
        return True
    if raw == "false":
        return False
    return None


def parse_current_governance_xbrl(
    raw: bytes,
    *,
    symbol: str,
    report_date: str,
    source_url: str,
) -> dict[str, Any]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GF001GovernanceError(f"invalid shareholding XML: {exc}") from exc

    contexts = _contexts(root)
    facts = _fact_rows(root)

    promoter_state, promoter = _exact_aggregate(
        contexts,
        facts,
        family="PROMOTER_GROUP",
    )
    public_state, public = _exact_aggregate(
        contexts,
        facts,
        family="PUBLIC",
    )
    mf_state, mf = _exact_aggregate(
        contexts,
        facts,
        family="MUTUAL_FUND_UTI",
    )

    encumbrance = {
        key: _exact_boolean(facts, concept=concept)
        for key, concept in ENCUMBRANCE_CONCEPTS.items()
    }

    core_reason = None
    core_ready = True
    if promoter_state != "READY":
        core_ready = False
        core_reason = f"PROMOTER_{promoter_state}"
    elif public_state != "READY":
        core_ready = False
        core_reason = f"PUBLIC_{public_state}"
    elif promoter is None or public is None:
        core_ready = False
        core_reason = "PROMOTER_PUBLIC_VALUE_UNAVAILABLE"
    elif not 0.95 <= promoter + public <= 1.05:
        core_ready = False
        core_reason = "PROMOTER_PUBLIC_SUM_OUTSIDE_FROZEN_TOLERANCE"
    elif any(value is None for value in encumbrance.values()):
        core_ready = False
        core_reason = "ENCUMBRANCE_BOOLEAN_UNAVAILABLE"

    return {
        "symbol": symbol,
        "report_date": report_date,
        "source_url": source_url,
        "raw_sha256": sha256_bytes(raw),
        "parser_status": "CORE_READY" if core_ready else "CORE_PARSE_FAILED",
        "core_failure_reason": core_reason,
        "promoter_state": promoter_state,
        "promoter_percentage": promoter * 100.0 if promoter is not None else None,
        "public_state": public_state,
        "public_percentage": public * 100.0 if public is not None else None,
        "mutual_fund_state": mf_state,
        "mutual_fund_percentage": mf * 100.0 if mf is not None else None,
        "promoter_encumbrance": encumbrance,
        "promoter_public_sum_fraction": (
            promoter + public
            if promoter is not None and public is not None
            else None
        ),
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def _validate_d002(census: dict[str, Any]) -> list[dict[str, Any]]:
    if census.get("census_id") != EXPECTED_D002_ID:
        raise AlphaContractError("GF001 D002 requires frozen SS001-D002 census")
    if census.get("census_sha256") != EXPECTED_D002_SHA:
        raise AlphaContractError("GF001 D002 SS001-D002 census SHA mismatch")
    if census.get("identity_count") != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("GF001 D002 identity count mismatch")
    if census.get("ready_latest_source_count") != EXPECTED_READY_LATEST:
        raise AlphaContractError("GF001 D002 ready-latest count mismatch")
    if census.get("adjacent_quarter_source_count") != EXPECTED_ADJACENT:
        raise AlphaContractError("GF001 D002 adjacent count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"GF001 D002 requires source {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("GF001 D002 source rows unavailable")
    return rows


def build_full_governance_panel(
    *,
    d002_census: dict[str, Any],
    latest_results: list[dict[str, Any]],
    prior_results: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    source_rows = _validate_d002(d002_census)
    source_by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in source_rows
        if isinstance(row, dict)
    }
    if len(source_by_symbol) != EXPECTED_IDENTITY_COUNT:
        raise AlphaContractError("GF001 D002 duplicate source symbols")

    latest_by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in latest_results
        if isinstance(row, dict)
    }
    prior_by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in prior_results
        if isinstance(row, dict)
    }

    expected_latest_symbols = {
        symbol
        for symbol, row in source_by_symbol.items()
        if row.get("source_state") == "READY"
    }
    if set(latest_by_symbol) != expected_latest_symbols:
        raise AlphaContractError("GF001 D002 latest parser result accounting mismatch")

    expected_prior_symbols = {
        symbol
        for symbol, row in source_by_symbol.items()
        if row.get("source_state") == "READY"
        and row.get("has_adjacent_prior") is True
    }
    if set(prior_by_symbol) != expected_prior_symbols:
        raise AlphaContractError("GF001 D002 prior parser result accounting mismatch")

    rows = []
    latest_core_ready = 0
    adjacent_core_ready = 0
    latest_failure_reasons: Counter[str] = Counter()
    prior_failure_reasons: Counter[str] = Counter()
    mf_states: Counter[str] = Counter()
    encumbrance_true_counts: Counter[str] = Counter()

    for symbol in sorted(source_by_symbol):
        source = source_by_symbol[symbol]
        if source.get("source_state") != "READY":
            rows.append(
                {
                    "symbol": symbol,
                    "source_state": source.get("source_state"),
                    "governance_state": "SOURCE_UNAVAILABLE",
                    "latest": None,
                    "prior": None,
                    "ownership_delta_pp": None,
                    "return_outcomes_opened": False,
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
            continue

        latest = latest_by_symbol[symbol]
        latest_ready = latest.get("status") == "READY" and (
            latest.get("governance", {}).get("parser_status") == "CORE_READY"
        )
        latest_governance = latest.get("governance") if latest.get("status") == "READY" else None

        if latest_ready:
            latest_core_ready += 1
            assert isinstance(latest_governance, dict)
            mf_states[str(latest_governance.get("mutual_fund_state"))] += 1
            enc = latest_governance.get("promoter_encumbrance")
            if isinstance(enc, dict):
                for key, value in enc.items():
                    if value is True:
                        encumbrance_true_counts[key] += 1
        else:
            reason = str(
                latest.get("error")
                or (
                    latest_governance.get("core_failure_reason")
                    if isinstance(latest_governance, dict)
                    else None
                )
                or "UNKNOWN"
            )
            latest_failure_reasons[reason] += 1

        prior = prior_by_symbol.get(symbol)
        prior_ready = prior is not None and prior.get("status") == "READY" and (
            prior.get("governance", {}).get("parser_status") == "CORE_READY"
        )
        prior_governance = (
            prior.get("governance")
            if prior is not None and prior.get("status") == "READY"
            else None
        )

        if prior is not None and not prior_ready:
            reason = str(
                prior.get("error")
                or (
                    prior_governance.get("core_failure_reason")
                    if isinstance(prior_governance, dict)
                    else None
                )
                or "UNKNOWN"
            )
            prior_failure_reasons[reason] += 1

        delta = None
        if latest_ready and prior_ready:
            adjacent_core_ready += 1
            assert isinstance(latest_governance, dict)
            assert isinstance(prior_governance, dict)
            delta = {
                "promoter_percentage_points": (
                    latest_governance["promoter_percentage"]
                    - prior_governance["promoter_percentage"]
                ),
                "public_percentage_points": (
                    latest_governance["public_percentage"]
                    - prior_governance["public_percentage"]
                ),
                "mutual_fund_percentage_points": (
                    latest_governance["mutual_fund_percentage"]
                    - prior_governance["mutual_fund_percentage"]
                    if latest_governance.get("mutual_fund_state") == "READY"
                    and prior_governance.get("mutual_fund_state") == "READY"
                    else None
                ),
            }

        rows.append(
            {
                "symbol": symbol,
                "source_state": "READY",
                "governance_state": (
                    "CORE_READY" if latest_ready else "CORE_PARSE_FAILED"
                ),
                "latest": latest_governance,
                "prior": prior_governance,
                "ownership_delta_pp": delta,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    latest_ratio = latest_core_ready / EXPECTED_READY_LATEST
    adjacent_ratio = adjacent_core_ready / EXPECTED_ADJACENT

    threshold_passes = {
        "minimum_latest_core_ready_90pct": latest_ratio >= 0.90,
        "minimum_adjacent_core_ready_80pct": adjacent_ratio >= 0.80,
        "complete_identity_accounting": len(rows) == EXPECTED_IDENTITY_COUNT,
    }

    output = {
        "schema_version": 1,
        "panel_id": PANEL_ID,
        "classification": "FULL_MARKET_GOVERNANCE_OWNERSHIP_FACTS_NOT_SCORE",
        "captured_at_utc": captured_at_utc,
        "source_d002_census_sha256": EXPECTED_D002_SHA,
        "identity_count": EXPECTED_IDENTITY_COUNT,
        "ready_latest_source_count": EXPECTED_READY_LATEST,
        "adjacent_source_count": EXPECTED_ADJACENT,
        "latest_core_ready_count": latest_core_ready,
        "latest_core_ready_ratio": latest_ratio,
        "adjacent_core_ready_count": adjacent_core_ready,
        "adjacent_core_ready_ratio": adjacent_ratio,
        "latest_failure_reason_counts": dict(sorted(latest_failure_reasons.items())),
        "prior_failure_reason_counts": dict(sorted(prior_failure_reasons.items())),
        "mutual_fund_state_counts": dict(sorted(mf_states.items())),
        "promoter_encumbrance_true_counts": dict(
            sorted(encumbrance_true_counts.items())
        ),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_governance_event_layer": all(
            threshold_passes.values()
        ),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["panel_sha256"] = digest(output)
    return output
