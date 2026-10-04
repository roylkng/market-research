from __future__ import annotations

from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope

PILOT_ID = "SS002-L001-P1-v1"
EXPECTED_P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
EXPECTED_D003_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"
FAMILIES = (
    "BUYBACK",
    "OPEN_OFFER_CONTROL",
    "TENDER_OFFER",
    "DELISTING",
    "ASSET_SALE_DIVESTMENT",
)
PER_FAMILY = 6


def _validate_sources(p2: dict[str, Any], d003: dict[str, Any]) -> None:
    if p2.get("census_id") != "SS002-D001-P2-v1":
        raise AlphaContractError("L001 pilot requires P2 census")
    if p2.get("census_sha256") != EXPECTED_P2_SHA:
        raise AlphaContractError("L001 pilot P2 SHA mismatch")
    if d003.get("corpus_id") != "SS002-D003-v1":
        raise AlphaContractError("L001 pilot requires D003 corpus")
    if d003.get("corpus_sha256") != EXPECTED_D003_SHA:
        raise AlphaContractError("L001 pilot D003 SHA mismatch")
    if d003.get("promotion_allowed_to_l001") is not True:
        raise AlphaContractError("L001 pilot requires passed D003")
    for payload, label in ((p2, "P2"), (d003, "D003")):
        if payload.get("return_outcomes_opened") is not False:
            raise AlphaContractError(f"L001 pilot {label} returns must remain closed")
        if payload.get("portfolio_eligibility_allowed") is not False:
            raise AlphaContractError(f"L001 pilot {label} portfolio eligibility must be false")
        if payload.get("live_capital_allowed") is not False:
            raise AlphaContractError(f"L001 pilot {label} live capital must be false")


def select_pilot_sample(
    *,
    p2: dict[str, Any],
    d003: dict[str, Any],
) -> dict[str, Any]:
    _validate_sources(p2, d003)
    events = p2.get("events")
    docs = d003.get("documents")
    if not isinstance(events, list) or not isinstance(docs, list):
        raise AlphaContractError("L001 pilot source rows unavailable")

    ready_docs: dict[str, dict[str, Any]] = {}
    event_to_docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in docs:
        if not isinstance(doc, dict) or doc.get("extraction_state") != "READY":
            continue
        doc_id = str(doc.get("document_id") or "")
        if not doc_id or doc_id in ready_docs:
            raise AlphaContractError("L001 pilot D003 document IDs must be unique")
        ready_docs[doc_id] = doc
        event_ids = doc.get("event_ids")
        if not isinstance(event_ids, list):
            raise AlphaContractError(f"{doc_id}: D003 event_ids unavailable")
        for event_id in event_ids:
            event_to_docs[str(event_id)].append(doc)

    selections: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    for family in FAMILIES:
        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
                continue
            categories = event.get("special_situation_categories")
            if not isinstance(categories, list) or family not in categories:
                continue
            event_id = str(event.get("announcement_id") or "")
            for doc in sorted(
                event_to_docs.get(event_id, []),
                key=lambda row: str(row.get("document_id") or ""),
            ):
                candidates.append((event, doc))

        candidates.sort(key=lambda pair: str(pair[0].get("announcement_id") or ""))
        candidates.sort(
            key=lambda pair: str(pair[0].get("exchange_published_at_utc") or ""),
            reverse=True,
        )

        seen_symbols: set[str] = set()
        seen_docs: set[str] = set()
        chosen = 0
        for event, doc in candidates:
            symbol = str(event.get("symbol") or "").upper()
            doc_id = str(doc.get("document_id") or "")
            if not symbol or not doc_id:
                raise AlphaContractError("L001 pilot candidate lacks symbol/document")
            if symbol in seen_symbols or doc_id in seen_docs:
                continue
            seen_symbols.add(symbol)
            seen_docs.add(doc_id)
            selections.append(
                {
                    "family": family,
                    "family_rank": chosen + 1,
                    "symbol": symbol,
                    "announcement_id": str(event["announcement_id"]),
                    "exchange_published_at_utc": event.get(
                        "exchange_published_at_utc"
                    ),
                    "document_id": doc_id,
                    "source_url": doc.get("source_url"),
                    "segment_manifest_sha256": doc.get(
                        "segment_manifest_sha256"
                    ),
                    "segment_count": doc.get("segment_count"),
                    "document_event_ids": doc.get("event_ids"),
                    "document_symbols": doc.get("symbols"),
                    "document_categories": doc.get("categories"),
                }
            )
            chosen += 1
            if chosen == PER_FAMILY:
                break
        family_counts[family] = chosen

    expected_max = len(FAMILIES) * PER_FAMILY
    if len(selections) > expected_max:
        raise AlphaContractError("L001 pilot sample exceeds frozen maximum")

    output = {
        "schema_version": 1,
        "pilot_id": PILOT_ID,
        "classification": "DETERMINISTIC_LLM_EXTRACTION_PILOT_SAMPLE_NOT_ALPHA",
        "source_p2_sha256": EXPECTED_P2_SHA,
        "source_d003_sha256": EXPECTED_D003_SHA,
        "families": list(FAMILIES),
        "per_family_limit": PER_FAMILY,
        "family_counts": family_counts,
        "selected_document_count": len(selections),
        "selections": selections,
        "return_outcomes_opened": False,
        "model_inference_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["sample_sha256"] = digest(output)
    return output


def build_selected_prompt(
    *,
    selection: dict[str, Any],
    d003_document: dict[str, Any],
) -> dict[str, Any]:
    document_id = str(selection.get("document_id") or "")
    if d003_document.get("document_id") != document_id:
        raise AlphaContractError("L001 pilot document identity mismatch")
    if d003_document.get("extraction_state") != "READY":
        raise AlphaContractError("L001 pilot document must be TEXT_READY")
    if (
        d003_document.get("segment_manifest_sha256")
        != selection.get("segment_manifest_sha256")
    ):
        raise AlphaContractError("L001 pilot segment manifest mismatch")

    segments = d003_document.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AlphaContractError("L001 pilot READY document lacks segments")
    return build_prompt_envelope(
        document_id=document_id,
        source_url=str(selection.get("source_url") or ""),
        event_ids=[str(v) for v in selection.get("document_event_ids") or []],
        symbols=[str(v) for v in selection.get("document_symbols") or []],
        category_hints=[str(v) for v in selection.get("document_categories") or []],
        segments=segments,
        segment_manifest_sha256=str(selection["segment_manifest_sha256"]),
    )
