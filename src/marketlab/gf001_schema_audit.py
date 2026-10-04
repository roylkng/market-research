from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

AUDIT_ID = "GF001-D001-P1-v1"
EXPECTED_D002_ID = "SS001-D002-v1"
EXPECTED_D002_SHA = "214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293"
EXPECTED_SAMPLE_ID = "GF001-D001-CURRENT-SCHEMA-SAMPLE-v1"
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

ENCUMBRANCE_CONCEPTS = (
    "WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup",
    "WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup",
    "WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup",
)

KEYWORDS = (
    "promoter",
    "promoter group",
    "public",
    "encumber",
    "pledge",
    "mutual fund",
    "uti",
    "foreign portfolio",
    "fpi",
    "insurance",
    "institutional",
    "significant beneficial",
    "shareholder",
    "shareholding",
    "percentage",
    "number of shares",
)


class GF001SchemaError(ValueError):
    """Raised when current shareholding XBRL cannot be audited without guessing."""


@dataclass(frozen=True)
class ContextInfo:
    context_id: str
    instant: str | None
    start_date: str | None
    end_date: str | None
    explicit_members: tuple[tuple[str, str], ...]
    has_typed_member: bool


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
    return parsed if math.isfinite(parsed) else None


def _contexts(root: ET.Element) -> dict[str, ContextInfo]:
    result: dict[str, ContextInfo] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = str(element.attrib.get("id") or "").strip()
        if not context_id:
            continue
        instant = None
        start = None
        end = None
        explicit_members: list[tuple[str, str]] = []
        has_typed_member = False
        for child in element.iter():
            local = _local_name(child.tag)
            value = _clean(child.text)
            if local == "instant":
                instant = value or None
            elif local == "startDate":
                start = value or None
            elif local == "endDate":
                end = value or None
            elif local == "explicitMember":
                explicit_members.append(
                    (
                        _qname_local(child.attrib.get("dimension")),
                        _qname_local(child.text),
                    )
                )
            elif local == "typedMember":
                has_typed_member = True
        if context_id in result:
            raise GF001SchemaError(f"duplicate XBRL context id: {context_id}")
        result[context_id] = ContextInfo(
            context_id=context_id,
            instant=instant,
            start_date=start,
            end_date=end,
            explicit_members=tuple(sorted(explicit_members)),
            has_typed_member=has_typed_member,
        )
    return result


def _aggregate_family(context: ContextInfo) -> str | None:
    for family, (context_id, member) in AGGREGATE_CONTEXTS.items():
        if context.context_id != context_id or context.has_typed_member:
            continue
        if context.explicit_members == (("CategoryOfShareholdersAxis", member),):
            return family
    return None


def _keyword_hit(local_name: str, context_ref: str) -> bool:
    text = f"{local_name} {context_ref}".casefold()
    return any(token in text for token in KEYWORDS)


def _infer_scale(promoter: float, public: float) -> str:
    total = promoter + public
    if 0 <= promoter <= 1 and 0 <= public <= 1 and 0.95 <= total <= 1.05:
        return "FRACTION_0_TO_1"
    if 0 <= promoter <= 100 and 0 <= public <= 100 and 95 <= total <= 105:
        return "PERCENTAGE_POINTS_0_TO_100"
    return "UNRESOLVED"


def _boolean_fact(
    facts: list[dict[str, Any]],
    *,
    concept: str,
    context_ref: str,
) -> bool | None:
    matches = [
        row
        for row in facts
        if row["concept"] == concept and row["context_ref"] == context_ref
    ]
    if len(matches) != 1:
        return None
    raw = str(matches[0]["raw_value"]).strip().casefold()
    if raw == "true":
        return True
    if raw == "false":
        return False
    return None


def audit_shareholding_xbrl(
    raw: bytes,
    *,
    symbol: str,
    report_date: str,
    source_url: str,
) -> dict[str, Any]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GF001SchemaError(f"invalid shareholding XML: {exc}") from exc

    contexts = _contexts(root)
    aggregate_candidates: dict[str, list[dict[str, Any]]] = {
        family: [] for family in AGGREGATE_CONTEXTS
    }
    keyword_facts: list[dict[str, Any]] = []
    all_facts: list[dict[str, Any]] = []
    concept_counts: Counter[str] = Counter()
    context_counts: Counter[str] = Counter()
    fact_count = 0

    for element in root.iter():
        context_ref = str(
            element.attrib.get("contextRef")
            or element.attrib.get("contextref")
            or ""
        ).strip()
        if not context_ref:
            continue
        fact_count += 1
        local = _local_name(element.tag)
        unit_ref = str(
            element.attrib.get("unitRef")
            or element.attrib.get("unitref")
            or ""
        ).strip() or None
        raw_value = _clean(element.text)
        numeric = _number(raw_value)
        fact = {
            "concept": local,
            "context_ref": context_ref,
            "unit_ref": unit_ref,
            "raw_value": raw_value,
            "numeric_value": numeric,
        }
        all_facts.append(fact)
        concept_counts[local] += 1
        context_counts[context_ref] += 1

        context = contexts.get(context_ref)
        family = _aggregate_family(context) if context is not None else None
        if local == SHARE_PCT_CONCEPT and family is not None:
            aggregate_candidates[family].append(fact)

        if _keyword_hit(local, context_ref):
            keyword_facts.append(
                {
                    **fact,
                    "raw_value": raw_value[:200],
                }
            )

    aggregates: dict[str, dict[str, Any] | None] = {}
    aggregate_states: dict[str, str] = {}
    for family, (context_id, _) in AGGREGATE_CONTEXTS.items():
        rows = aggregate_candidates[family]
        context_present = context_id in contexts
        if len(rows) == 1 and rows[0]["numeric_value"] is not None:
            aggregates[family] = rows[0]
            aggregate_states[family] = "READY"
        elif not context_present:
            aggregates[family] = None
            aggregate_states[family] = "CATEGORY_CONTEXT_ABSENT"
        else:
            aggregates[family] = None
            aggregate_states[family] = "AMBIGUOUS_OR_INVALID"

    scale = "UNRESOLVED"
    promoter = aggregates["PROMOTER_GROUP"]
    public = aggregates["PUBLIC"]
    if promoter is not None and public is not None:
        scale = _infer_scale(
            float(promoter["numeric_value"]),
            float(public["numeric_value"]),
        )

    encumbrance_flags = {
        concept: _boolean_fact(
            all_facts,
            concept=concept,
            context_ref="MainI",
        )
        for concept in ENCUMBRANCE_CONCEPTS
    }
    encumbrance_ready = all(value is not None for value in encumbrance_flags.values())

    return {
        "symbol": symbol,
        "report_date": report_date,
        "source_url": source_url,
        "raw_sha256": sha256_bytes(raw),
        "well_formed": True,
        "context_count": len(contexts),
        "fact_count": fact_count,
        "aggregate_families": aggregates,
        "aggregate_states": aggregate_states,
        "aggregate_scale_semantics": scale,
        "promoter_aggregate_ready": promoter is not None,
        "public_aggregate_ready": public is not None,
        "mutual_fund_aggregate_ready": aggregates["MUTUAL_FUND_UTI"] is not None,
        "mutual_fund_aggregate_state": aggregate_states["MUTUAL_FUND_UTI"],
        "promoter_encumbrance_flags": encumbrance_flags,
        "promoter_encumbrance_ready": encumbrance_ready,
        "keyword_fact_count": len(keyword_facts),
        "keyword_facts": keyword_facts,
        "concept_counts": dict(sorted(concept_counts.items())),
        "context_counts": dict(sorted(context_counts.items())),
    }


def _validate_inputs(
    d002: dict[str, Any],
    sample: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if d002.get("census_id") != EXPECTED_D002_ID:
        raise AlphaContractError("GF001 D001 requires frozen SS001-D002 census")
    if d002.get("census_sha256") != EXPECTED_D002_SHA:
        raise AlphaContractError("GF001 D001 SS001-D002 census SHA mismatch")
    if d002.get("return_outcomes_opened") is not False:
        raise AlphaContractError("GF001 D001 refuses opened return outcomes")
    rows = d002.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("GF001 D001 D002 rows unavailable")
    by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in rows
        if isinstance(row, dict)
    }

    if sample.get("sample_id") != EXPECTED_SAMPLE_ID:
        raise AlphaContractError("GF001 D001 sample id mismatch")
    if sample.get("return_outcomes_opened") is not False:
        raise AlphaContractError("GF001 D001 sample must keep returns closed")
    sample_rows = sample.get("symbols")
    if not isinstance(sample_rows, list) or len(sample_rows) != 48:
        raise AlphaContractError("GF001 D001 requires frozen 48-symbol sample")
    symbols = [str(row.get("symbol") or "").upper() for row in sample_rows]
    if len(symbols) != len(set(symbols)):
        raise AlphaContractError("GF001 D001 sample symbols must be unique")
    return by_symbol, sample_rows


def build_schema_audit(
    *,
    d002_census: dict[str, Any],
    sample: dict[str, Any],
    filing_results: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    d002_by_symbol, sample_rows = _validate_inputs(d002_census, sample)
    expected_symbols = {str(row["symbol"]).upper() for row in sample_rows}
    result_by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in filing_results
        if isinstance(row, dict)
    }
    if set(result_by_symbol) != expected_symbols:
        raise AlphaContractError("GF001 D001 filing-result symbol accounting mismatch")

    source_alignment_failures = []
    parsed = []
    fetch_failures = []
    for sample_row in sample_rows:
        symbol = str(sample_row["symbol"]).upper()
        expected_date = str(sample_row["source_report_date"])
        d002_row = d002_by_symbol.get(symbol)
        if not isinstance(d002_row, dict) or d002_row.get("source_state") != "READY":
            source_alignment_failures.append(symbol)
            continue
        latest = d002_row.get("latest")
        if not isinstance(latest, dict) or latest.get("report_date") != expected_date:
            source_alignment_failures.append(symbol)
            continue

        result = result_by_symbol[symbol]
        if result.get("status") == "READY":
            parsed.append(result["audit"])
        else:
            fetch_failures.append(
                {
                    "symbol": symbol,
                    "status": result.get("status"),
                    "error": result.get("error"),
                }
            )

    if source_alignment_failures:
        raise AlphaContractError(
            "GF001 D001 frozen sample no longer aligns with D002: "
            + ",".join(sorted(source_alignment_failures))
        )

    june = [row for row in parsed if row["report_date"] == "2026-06-30"]
    sept = [row for row in parsed if row["report_date"] == "2026-09-30"]

    def ratio(rows: list[dict[str, Any]], field: str) -> float:
        if not rows:
            return 0.0
        return sum(row.get(field) is True for row in rows) / len(rows)

    june_promoter = ratio(june, "promoter_aggregate_ready")
    june_public = ratio(june, "public_aggregate_ready")
    june_encumbrance = ratio(june, "promoter_encumbrance_ready")
    resolved_scale_ratio = ratio(
        [
            {
                "resolved": row.get("aggregate_scale_semantics") != "UNRESOLVED",
            }
            for row in parsed
        ],
        "resolved",
    )

    present_mf = [
        row for row in parsed
        if row.get("mutual_fund_aggregate_state") != "CATEGORY_CONTEXT_ABSENT"
    ]
    mf_present_parseable = bool(present_mf) and all(
        row.get("mutual_fund_aggregate_state") == "READY" for row in present_mf
    )

    sept_core_ready = (
        len(sept) == 6
        and all(
            row.get("promoter_aggregate_ready")
            and row.get("public_aggregate_ready")
            and row.get("promoter_encumbrance_ready")
            and row.get("aggregate_scale_semantics") != "UNRESOLVED"
            for row in sept
        )
    )

    concept_file_counts: Counter[str] = Counter()
    context_file_counts: Counter[str] = Counter()
    scale_counts: Counter[str] = Counter()
    mf_state_counts: Counter[str] = Counter()
    keyword_concept_counts: Counter[str] = Counter()
    keyword_context_counts: Counter[str] = Counter()

    for row in parsed:
        concept_file_counts.update(row["concept_counts"].keys())
        context_file_counts.update(row["context_counts"].keys())
        scale_counts[row["aggregate_scale_semantics"]] += 1
        mf_state_counts[row["mutual_fund_aggregate_state"]] += 1
        keyword_concept_counts.update(
            {item["concept"] for item in row["keyword_facts"]}
        )
        keyword_context_counts.update(
            {item["context_ref"] for item in row["keyword_facts"]}
        )

    threshold_passes = {
        "minimum_44_well_formed": len(parsed) >= 44,
        "june_promoter_aggregate_90pct": june_promoter >= 0.90,
        "june_public_aggregate_90pct": june_public >= 0.90,
        "june_encumbrance_flags_90pct": june_encumbrance >= 0.90,
        "present_mutual_fund_contexts_parseable": mf_present_parseable,
        "september_core_semantics_ready": sept_core_ready,
        "aggregate_scale_resolved_90pct": resolved_scale_ratio >= 0.90,
    }

    output = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "CURRENT_SHAREHOLDING_XBRL_SCHEMA_AUDIT_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_d002_census_sha256": EXPECTED_D002_SHA,
        "sample_id": EXPECTED_SAMPLE_ID,
        "sample_count": len(sample_rows),
        "ready_parse_count": len(parsed),
        "fetch_or_parse_failure_count": len(fetch_failures),
        "fetch_or_parse_failures": fetch_failures,
        "june_2026_ready_count": len(june),
        "september_2026_ready_count": len(sept),
        "june_promoter_aggregate_ready_ratio": june_promoter,
        "june_public_aggregate_ready_ratio": june_public,
        "june_encumbrance_ready_ratio": june_encumbrance,
        "mutual_fund_aggregate_state_counts": dict(sorted(mf_state_counts.items())),
        "aggregate_scale_resolved_ratio": resolved_scale_ratio,
        "aggregate_scale_semantics_counts": dict(sorted(scale_counts.items())),
        "concept_file_counts": dict(sorted(concept_file_counts.items())),
        "context_file_counts": dict(sorted(context_file_counts.items())),
        "keyword_concept_file_counts": dict(sorted(keyword_concept_counts.items())),
        "keyword_context_file_counts": dict(sorted(keyword_context_counts.items())),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_gf001_d002_parser": all(threshold_passes.values()),
        "filings": sorted(parsed, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["audit_sha256"] = digest(output)
    return output
