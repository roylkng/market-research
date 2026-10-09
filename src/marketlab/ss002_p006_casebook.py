from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PACK_ID = "SS002-P006-v1"
P003_ID = "SS002-P003-v1"
P003_SHA = "7abbe52043b7ef3de89cb617d4fba2b181c3d8c4978df7a29ea557eab54469f7"
P004_ID = "SS002-P004-NATIVE-8DOC-v1"
P004_SHA = "03d8ae16dd642e8e107b62bdb03eb9dc7e178d0327d742586bc35b65de943ff3"
P005_ID = "SS002-P005-v1"
P005_SHA = "2175f575542682949ca76b696b0aee1064d375937c3f7f12b314e41bcf57b418"
HG001_SHA = "79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff"
HA001_SHA = "81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3"

EXPECTED_SYMBOLS = frozenset(
    {
        "VRLLOG", "PVRINOX", "OLAELEC", "SAMBHV", "INOXGREEN",
        "KOTHARIPET", "PREMEXPLN", "TVSSRICHAK",
    }
)


def _require_false(source: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    for field in fields:
        if source.get(field) is not False:
            raise AlphaContractError(f"{label} must have {field}=false")


def _unique_index(rows: Any, field: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise TypeError(f"{label} rows must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{label} row must be an object")
        key = row.get(field)
        if not isinstance(key, str) or not key or key in result:
            raise AlphaContractError(f"{label} {field} is missing or repeated")
        result[key] = row
    return result


def _verify_sources(
    p003: dict[str, Any],
    p004: dict[str, Any],
    p005: dict[str, Any],
    hg001: dict[str, Any],
    ha001: dict[str, Any],
) -> None:
    checks = (
        (p003, "corpus_id", P003_ID, "P003"),
        (p003, "corpus_sha256", P003_SHA, "P003"),
        (p004, "pilot_id", P004_ID, "P004"),
        (p004, "pilot_sha256", P004_SHA, "P004"),
        (p005, "gate_id", P005_ID, "P005"),
        (p005, "gate_sha256", P005_SHA, "P005"),
        (hg001, "router_sha256", HG001_SHA, "HG001"),
        (ha001, "panel_sha256", HA001_SHA, "HA001"),
    )
    for source, field, expected, label in checks:
        if source.get(field) != expected:
            raise AlphaContractError(f"{label} {field} identity mismatch")
    for name, source in (
        ("P003", p003), ("P004", p004), ("P005", p005),
        ("HG001", hg001), ("HA001", ha001),
    ):
        _require_false(
            source,
            ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"),
            name,
        )


def build_p006_casebook(
    *,
    p003_corpus: dict[str, Any],
    p003_documents: dict[str, dict[str, Any]],
    p004_pilot: dict[str, Any],
    p005_gate: dict[str, Any],
    hg001_router: dict[str, Any],
    ha001_panel: dict[str, Any],
) -> dict[str, Any]:
    _verify_sources(p003_corpus, p004_pilot, p005_gate, hg001_router, ha001_panel)

    p004 = _unique_index(p004_pilot.get("cases"), "symbol", "P004")
    p005 = _unique_index(p005_gate.get("cases"), "symbol", "P005")
    market = _unique_index(hg001_router.get("rows"), "symbol", "HG001")
    assets = _unique_index(ha001_panel.get("rows"), "symbol", "HA001")
    doc_catalog = _unique_index(p003_corpus.get("documents"), "document_id", "P003")
    # P003 may have explicitly unfetched documents with null IDs; index only READY entries.
    if set(p004) != EXPECTED_SYMBOLS or set(p005) != EXPECTED_SYMBOLS:
        raise AlphaContractError("P006 must retain exactly the frozen eight symbols")
    if set(p003_documents) != {p004[symbol]["document_id"] for symbol in p004}:
        raise AlphaContractError("P006 must receive precisely the eight frozen source documents")

    cases = []
    total_explicit = 0
    total_citations = 0
    for symbol in sorted(EXPECTED_SYMBOLS):
        upstream = p004[symbol]
        routed = p005[symbol]
        document_id = upstream["document_id"]
        if document_id != routed.get("document_id") or symbol not in market or symbol not in assets:
            raise AlphaContractError(f"{symbol}: source, lane or issuer context mismatch")
        extracted = upstream.get("validated_extraction")
        source = p003_documents[document_id]
        catalog = doc_catalog.get(document_id)
        if not isinstance(extracted, dict) or not isinstance(source, dict) or catalog is None:
            raise AlphaContractError(f"{symbol}: validated extraction or source unavailable")
        if extracted.get("document_id") != document_id or source.get("document_id") != document_id:
            raise AlphaContractError(f"{symbol}: document identity mismatch")
        if upstream.get("source_url") != source.get("source_url"):
            raise AlphaContractError(f"{symbol}: official document URL mismatch")
        if source.get("segment_manifest_sha256") != extracted.get("provenance", {}).get(
            "input_segment_manifest_sha256"
        ):
            raise AlphaContractError(f"{symbol}: text segment manifest SHA mismatch")

        segments = _unique_index(source.get("segments"), "segment_id", "P003 segments")
        for seg in segments.values():
            text = seg.get("text")
            sha = seg.get("text_sha256")
            if not isinstance(text, str) or not isinstance(sha, str):
                raise AlphaContractError(f"{symbol}: text segment fields missing")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != sha:
                raise AlphaContractError(f"{symbol}: segment text SHA mismatch")

        claims = []
        blocks = extracted.get("facts")
        if not isinstance(blocks, dict):
            raise AlphaContractError(f"{symbol}: validated facts unavailable")
        for family, facts in sorted(blocks.items()):
            if not isinstance(facts, dict):
                raise TypeError(f"{symbol}: fact family must be a dictionary")
            for name, fact in sorted(facts.items()):
                if not isinstance(fact, dict):
                    raise TypeError(f"{symbol}: fact must be an object")
                if fact.get("status") != "EXPLICIT":
                    if fact.get("status") != "UNKNOWN" or fact.get("value") is not None:
                        raise AlphaContractError(f"{symbol}: unknown fact is not null")
                    continue
                refs = fact.get("evidence_segment_ids")
                if not isinstance(refs, list) or not refs:
                    raise AlphaContractError(f"{symbol}: explicit claim lacks citations")
                cited = []
                for ref in refs:
                    if ref not in segments:
                        raise AlphaContractError(f"{symbol}: claim cites missing segment {ref}")
                    seg = segments[ref]
                    locator = seg.get("locator")
                    cited.append(
                        {
                            "segment_id": ref,
                            "segment_text_sha256": seg["text_sha256"],
                            "locator": locator,
                            "source_char_count": seg.get("char_count"),
                            "semantic_support_verified": False,
                        }
                    )
                claims.append(
                    {
                        "field_path": f"{family}.{name}",
                        "extracted_value": fact.get("value"),
                        "extracted_unit": fact.get("unit"),
                        "cited_segments": cited,
                        "citation_integrity_verified": True,
                        "independent_semantic_verification": "PENDING",
                    }
                )
                total_citations += len(cited)

        if len(claims) != upstream.get("explicit_fact_count"):
            raise AlphaContractError(f"{symbol}: explicit fact count mismatch")
        total_explicit += len(claims)
        market_row = market[symbol]
        asset_row = assets[symbol]
        if market_row.get("isin") != asset_row.get("isin"):
            raise AlphaContractError(f"{symbol}: independent full-market ISIN mismatch")
        if routed.get("independent_semantic_audit") != "PENDING":
            raise AlphaContractError(f"{symbol}: P005 semantic audit state changed")
        if routed.get("underwriting_ready") is not False:
            raise AlphaContractError(f"{symbol}: P005 unexpectedly underwritten")

        details = source.get("details")
        if not isinstance(details, dict):
            raise AlphaContractError(f"{symbol}: source document page details missing")

        cases.append(
            {
                "symbol": symbol,
                "isin": market_row["isin"],
                "document_id": document_id,
                "source_url": source["source_url"],
                "source_segment_manifest_sha256": source["segment_manifest_sha256"],
                "source_page_count": details.get("page_count"),
                "source_empty_page_count": details.get("empty_page_count"),
                "source_failed_page_count": details.get("failed_page_count"),
                "requires_visual_review": bool(
                    details.get("empty_page_count") or details.get("failed_page_count")
                    or extracted.get("economic_relevance") == "UNKNOWN"
                ),
                "economic_relevance_model_label": extracted.get("economic_relevance"),
                "transaction_families_model_labels": extracted.get("transaction_families"),
                "transaction_stage_model_label": extracted.get("transaction_stage"),
                "research_lane": routed.get("research_lane"),
                "active_transaction_research_lens": routed.get("active_transaction_research_lens"),
                "unverified_evidence_requirements": routed.get("unverified_evidence_requirements"),
                "pre_event_market_context_as_of": "2026-10-01",
                "pre_event_research_route": market_row.get("research_route"),
                "pre_event_active_lanes": market_row.get("active_opportunity_lanes"),
                "pre_event_liquidity_band": market_row.get("liquidity_band"),
                "pre_event_median_daily_turnover_inr": market_row.get("median_daily_turnover_inr"),
                "pre_event_governance_caution_flags": market_row.get("governance_caution_flags"),
                "pre_event_asset_opportunity_flags": asset_row.get("opportunity_flags"),
                "pre_event_asset_caution_flags": asset_row.get("caution_flags"),
                "explicit_fact_count": len(claims),
                "claims": claims,
                "independent_semantic_audit_complete": False,
                "share_action_clearance_proven": False,
                "current_entry_price_verified": False,
                "underwriting_ready": False,
                "expected_return_modeled": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    if total_explicit != 52:
        raise AlphaContractError(f"P006 expected 52 explicit facts, found {total_explicit}")
    state_counts = Counter(row["research_lane"] for row in cases)
    output = {
        "schema_version": 1,
        "pack_id": PACK_ID,
        "classification": "DOCUMENT_CITATION_AND_PRE_EVENT_CONTEXT_NOT_AUDIT_OR_ALPHA",
        "sources": {
            "p003_corpus_sha256": P003_SHA,
            "p004_pilot_sha256": P004_SHA,
            "p005_gate_sha256": P005_SHA,
            "hg001_router_sha256": HG001_SHA,
            "ha001_panel_sha256": HA001_SHA,
        },
        "case_count": len(cases),
        "explicit_fact_count": total_explicit,
        "cited_segment_reference_count": total_citations,
        "case_lane_counts": dict(sorted(state_counts.items())),
        "cases": cases,
        "independent_semantic_audit_complete": False,
        "current_entry_prices_verified": False,
        "share_action_clearance_proven": False,
        "underwriting_ready_count": 0,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["pack_sha256"] = digest(output)
    return output
