from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PANEL_ID = "SS001-D004-v1"
GF001_PANEL_ID = "GF001-D002-v1"
EXPECTED_GF001_SHA = "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
EXPECTED_IDENTITIES = 2319
EXPECTED_LATEST_SOURCES = 2050
GROUP_CONTEXTS = (
    "ShareholdingOfPromoterAndPromoterGroup_ContextI",
    "PublicShareholding_ContextI",
    "EmployeeBenefitsTrusts_ContextI",
)
SHARES_CONCEPT = "NumberOfShares"
FRACTION_CONCEPT = "ShareholdingAsAPercentageOfTotalNumberOfShares"
PARTLY_PAID_CONCEPT = "WhetherTheListedEntityHasIssuedAnyPartlyPaidUpShares"
FRACTION_SUM_TOLERANCE = Decimal("0.001")
CATEGORY_FRACTION_TOLERANCE = Decimal("0.0015")


class ShareCountSourceError(ValueError):
    """Exact NSE share-count fact cannot be safely interpreted."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _unique_value(
    values: dict[tuple[str, str], set[str]],
    context: str,
    concept: str,
) -> str | None:
    observed = values.get((context, concept), set())
    if len(observed) > 1:
        raise ShareCountSourceError(f"conflicting {concept} values in {context}")
    return next(iter(observed)) if observed else None


def _decimal(value: str, *, kind: str) -> Decimal:
    try:
        parsed = Decimal(value.strip().replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ShareCountSourceError(f"invalid {kind} source value") from exc
    if not parsed.is_finite():
        raise ShareCountSourceError(f"nonfinite {kind} source value")
    return parsed


def extract_share_counts(raw: bytes, *, expected_sha256: str) -> dict[str, Any]:
    observed_sha = hashlib.sha256(raw).hexdigest()
    if observed_sha != expected_sha256:
        raise ShareCountSourceError("raw source SHA-256 mismatch")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ShareCountSourceError("shareholding source is not well-formed XML") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise ShareCountSourceError("shareholding source is not XBRL")

    contexts: set[str] = set()
    facts: dict[tuple[str, str], set[str]] = {}
    for item in root.iter():
        if _local_name(item.tag).casefold() == "context" and item.attrib.get("id"):
            contexts.add(item.attrib["id"])
        context = item.attrib.get("contextRef")
        if not context:
            continue
        concept = _local_name(item.tag)
        if concept not in {SHARES_CONCEPT, FRACTION_CONCEPT, PARTLY_PAID_CONCEPT}:
            continue
        text = (item.text or "").strip()
        if text:
            facts.setdefault((context, concept), set()).add(text)

    groups: dict[str, dict[str, Any]] = {}
    total_shares = 0
    total_fraction = Decimal(0)
    for context in GROUP_CONTEXTS:
        present = context in contexts
        if not present and context == GROUP_CONTEXTS[2]:
            continue
        if not present:
            raise ShareCountSourceError(f"required aggregate context absent: {context}")
        count_text = _unique_value(facts, context, SHARES_CONCEPT)
        percent_text = _unique_value(facts, context, FRACTION_CONCEPT)
        if count_text is None or percent_text is None:
            raise ShareCountSourceError(f"incomplete category count/fraction: {context}")
        count_number = _decimal(count_text, kind="share count")
        fraction = _decimal(percent_text, kind="ownership fraction")
        if count_number < 0 or count_number != count_number.to_integral_value():
            raise ShareCountSourceError(f"invalid integer share count: {context}")
        if fraction < 0 or fraction > 1:
            raise ShareCountSourceError(f"ownership fraction outside [0,1]: {context}")
        count = int(count_number)
        groups[context] = {"share_count": count, "reported_fraction": float(fraction)}
        total_shares += count
        total_fraction += fraction

    if total_shares <= 0:
        raise ShareCountSourceError("aggregate share count is not positive")
    if abs(total_fraction - Decimal(1)) > FRACTION_SUM_TOLERANCE:
        raise ShareCountSourceError("aggregate ownership fractions fail sum-to-one")
    for context, group in groups.items():
        observed = Decimal(group["share_count"]) / Decimal(total_shares)
        reported = Decimal(str(group["reported_fraction"]))
        if abs(observed - reported) > CATEGORY_FRACTION_TOLERANCE:
            raise ShareCountSourceError(f"aggregate count/fraction mismatch: {context}")

    flag = _unique_value(facts, "MainI", PARTLY_PAID_CONCEPT)
    flag_normalized = flag.casefold() if flag else "unknown"
    if flag_normalized not in {"true", "false", "unknown"}:
        raise ShareCountSourceError("invalid partly-paid source flag")

    return {
        "status": "SHARE_COUNT_READY",
        "reported_share_count": total_shares,
        "aggregate_fraction_sum": float(total_fraction),
        "categories": groups,
        "employee_trust_category_state": (
            "PRESENT" if GROUP_CONTEXTS[2] in groups else "STRUCTURALLY_ABSENT"
        ),
        "partly_paid_flag": flag_normalized.upper(),
        "capitalization_source_eligible": flag_normalized == "false",
        "raw_sha256": observed_sha,
        "error": None,
    }


def _validate_gf001(panel: dict[str, Any]) -> list[dict[str, Any]]:
    if panel.get("panel_id") != GF001_PANEL_ID:
        raise AlphaContractError("D004 requires frozen GF001-D002 panel")
    if panel.get("panel_sha256") != EXPECTED_GF001_SHA:
        raise AlphaContractError("D004 GF001 source panel SHA mismatch")
    if panel.get("identity_count") != EXPECTED_IDENTITIES:
        raise AlphaContractError("D004 frozen identity count mismatch")
    if panel.get("ready_latest_source_count") != EXPECTED_LATEST_SOURCES:
        raise AlphaContractError("D004 frozen latest-source count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if panel.get(field) is not False:
            raise AlphaContractError(f"D004 requires GF001 {field}=false")
    rows = panel.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_IDENTITIES:
        raise AlphaContractError("D004 source identity rows unavailable")
    return rows


def build_share_count_panel(
    *,
    gf001_panel: dict[str, Any],
    extracted_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    source_rows = _validate_gf001(gf001_panel)
    source_index = {str(row.get("symbol") or ""): row for row in source_rows}
    if len(source_index) != EXPECTED_IDENTITIES:
        raise AlphaContractError("D004 source symbols are not unique")

    extracted_index: dict[str, dict[str, Any]] = {}
    for row in extracted_rows:
        symbol = str(row.get("symbol") or "")
        if symbol in extracted_index or not symbol:
            raise AlphaContractError("D004 extracted symbol missing/duplicated")
        extracted_index[symbol] = row

    ready_source_symbols = {
        symbol
        for symbol, row in source_index.items()
        if row.get("source_state") == "READY"
    }
    if len(ready_source_symbols) != EXPECTED_LATEST_SOURCES:
        raise AlphaContractError("D004 READY source accounting mismatch")
    if set(extracted_index) != ready_source_symbols:
        raise AlphaContractError("D004 extracted/source symbol accounting mismatch")

    output_rows = []
    status_counts: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    ready_count = 0
    capitalization_ready_count = 0

    for symbol, source in sorted(source_index.items()):
        is_source_ready = symbol in ready_source_symbols
        latest = source.get("latest") if is_source_ready else None
        parsed = extracted_index.get(symbol)
        status = parsed.get("status") if parsed else "SOURCE_UNAVAILABLE"
        status_counts[str(status)] += 1
        if status == "SHARE_COUNT_READY":
            if not is_source_ready or not isinstance(latest, dict) or not parsed:
                raise AlphaContractError("D004 READY count without approved source")
            if parsed.get("raw_sha256") != latest.get("raw_sha256"):
                raise AlphaContractError(f"D004 source hash mismatch for {symbol}")
            if not isinstance(parsed.get("reported_share_count"), int):
                raise AlphaContractError(f"D004 READY share count is not integer: {symbol}")
            ready_count += 1
            if parsed.get("capitalization_source_eligible") is True:
                capitalization_ready_count += 1
        elif parsed:
            errors[str(parsed.get("error") or "UNKNOWN")] += 1

        output_rows.append(
            {
                "symbol": symbol,
                "source_state": source.get("source_state"),
                "status": status,
                "report_date": latest.get("report_date") if latest else None,
                "source_url": latest.get("source_url") if latest else None,
                "raw_sha256": parsed.get("raw_sha256") if parsed else None,
                "reported_share_count": parsed.get("reported_share_count") if parsed else None,
                "aggregate_fraction_sum": parsed.get("aggregate_fraction_sum") if parsed else None,
                "employee_trust_category_state": (
                    parsed.get("employee_trust_category_state") if parsed else None
                ),
                "partly_paid_flag": parsed.get("partly_paid_flag") if parsed else None,
                "capitalization_source_eligible": bool(
                    parsed and parsed.get("capitalization_source_eligible") is True
                ),
                "error": parsed.get("error") if parsed else "NO_READY_SHAREHOLDING_SOURCE",
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    thresholds = {
        "all_2319_identities_accounted": len(output_rows) == EXPECTED_IDENTITIES,
        "all_2050_latest_sources_accounted": len(extracted_index) == EXPECTED_LATEST_SOURCES,
        "at_least_90pct_share_counts": ready_count / EXPECTED_LATEST_SOURCES >= 0.90,
        "at_least_85pct_capitalization_eligible": (
            capitalization_ready_count / EXPECTED_LATEST_SOURCES >= 0.85
        ),
        "every_ready_count_sha_verified": all(
            row["raw_sha256"] is not None
            for row in output_rows
            if row["status"] == "SHARE_COUNT_READY"
        ),
    }
    result = {
        "schema_version": 1,
        "diagnostic_id": PANEL_ID,
        "classification": "FULL_MARKET_SHARE_COUNT_SOURCE_FEASIBILITY_NOT_MARKET_CAP",
        "captured_at_utc": captured_at_utc,
        "source_gf001_panel_sha256": EXPECTED_GF001_SHA,
        "identity_count": EXPECTED_IDENTITIES,
        "latest_source_count": EXPECTED_LATEST_SOURCES,
        "share_count_ready_count": ready_count,
        "share_count_ready_ratio": ready_count / EXPECTED_LATEST_SOURCES,
        "capitalization_source_eligible_count": capitalization_ready_count,
        "capitalization_source_eligible_ratio": (
            capitalization_ready_count / EXPECTED_LATEST_SOURCES
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "failure_reason_counts": dict(sorted(errors.items())),
        "threshold_passes": thresholds,
        "feasibility_pass": all(thresholds.values()),
        "promotion_allowed_to_point_in_time_market_cap_design": all(thresholds.values()),
        "rows": output_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    result["panel_sha256"] = digest(result)
    return result
