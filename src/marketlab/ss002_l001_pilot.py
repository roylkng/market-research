from __future__ import annotations

from collections import Counter
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope

SELECTION_ID = "SS002-L001-P1-SELECTION-v1"
EXPECTED_P2_ID = "SS002-D001-P2-v1"
EXPECTED_P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
EXPECTED_D3_ID = "SS002-D003-v1"
EXPECTED_D3_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"

FAMILIES = (
    "BUYBACK",
    "OPEN_OFFER_CONTROL",
    "TENDER_OFFER",
    "DELISTING",
    "ASSET_SALE_DIVESTMENT",
)
PER_FAMILY = 6


def _validate_inputs(p2: dict[str, Any], d3: dict[str, Any]) -> None:
    if p2.get("census_id") != EXPECTED_P2_ID or p2.get("census_sha256") != EXPECTED_P2_SHA:
        raise AlphaContractError("SS002 L001 pilot P2 source mismatch")
    if d3.get("corpus_id") != EXPECTED_D3_ID or d3.get("corpus_sha256") != EXPECTED_D3_SHA:
        raise AlphaContractError("SS002 L001 pilot D3 source mismatch")
    for payload, label in ((p2, "P2"), (d3, "D3")):
        for field in (
            "return_outcomes_opened",
            "model_fitted",
            "portfolio_eligibility_allowed",
            "live_capital_allowed",
        ):
            if payload.get(field) is not False:
                raise AlphaContractError(f"SS002 L001 pilot requires {label} {field}=false")


def _document_index(d3: dict[str, Any]) -> dict[str, dict[str, Any]]:
    docs=d3.get("documents")
    if not isinstance(docs,list):
        raise AlphaContractError("SS002 L001 pilot D3 documents unavailable")
    by_url={}
    for row in docs:
        if not isinstance(row,dict):
            raise TypeError("SS002 L001 pilot D3 document row must be object")
        if row.get("extraction_state")!="READY":
            continue
        url=str(row.get("source_url") or "")
        if not url or url in by_url:
            raise AlphaContractError("SS002 L001 pilot D3 READY URLs must be unique")
        by_url[url]=row
    return by_url


def select_pilot(p2: dict[str, Any], d3: dict[str, Any]) -> dict[str, Any]:
    _validate_inputs(p2,d3)
    events=p2.get("events")
    if not isinstance(events,list):
        raise AlphaContractError("SS002 L001 pilot P2 events unavailable")
    docs=_document_index(d3)

    selected=[]
    family_counts=Counter()
    for family in FAMILIES:
        candidates=[]
        for event in events:
            if not isinstance(event,dict):
                raise TypeError("SS002 L001 pilot P2 event must be object")
            if event.get("mapping_state")!="CURRENT_INVESTABLE_IDENTITY":
                continue
            categories=event.get("special_situation_categories")
            if not isinstance(categories,list) or family not in categories:
                continue
            url=str(event.get("approved_attachment_url") or "")
            doc=docs.get(url)
            if doc is None:
                continue
            candidates.append((event,doc))

        candidates.sort(
            key=lambda pair: (
                str(pair[0].get("exchange_published_at_utc") or ""),
                # reverse timestamp is implemented by reverse=True below;
                # announcement id remains ascending through the second stable sort.
            ),
            reverse=True,
        )
        # Freeze announcement-id ascending within equal timestamps.
        grouped={}
        for event,doc in candidates:
            ts=str(event.get("exchange_published_at_utc") or "")
            grouped.setdefault(ts,[]).append((event,doc))
        ordered=[]
        for ts in sorted(grouped,reverse=True):
            ordered.extend(sorted(grouped[ts],key=lambda pair:str(pair[0].get("announcement_id") or "")))

        seen_symbols=set()
        seen_documents=set()
        for event,doc in ordered:
            symbol=str(event.get("symbol") or "").upper()
            document_id=str(doc.get("document_id") or "")
            if not symbol or not document_id:
                raise AlphaContractError("SS002 L001 pilot candidate identity incomplete")
            if symbol in seen_symbols or document_id in seen_documents:
                continue
            seen_symbols.add(symbol)
            seen_documents.add(document_id)

            segments=doc.get("segments")
            if not isinstance(segments,list) or not segments:
                raise AlphaContractError(f"{document_id}: READY document has no segments")
            prompt=build_prompt_envelope(
                document_id=document_id,
                source_url=str(doc["source_url"]),
                event_ids=[str(value) for value in doc.get("event_ids",[])],
                symbols=[str(value) for value in doc.get("symbols",[])],
                category_hints=[str(value) for value in doc.get("categories",[])],
                segments=segments,
                segment_manifest_sha256=str(doc.get("segment_manifest_sha256") or ""),
            )
            selected.append(
                {
                    "pilot_family": family,
                    "exchange_published_at_utc": event.get("exchange_published_at_utc"),
                    "announcement_id": event.get("announcement_id"),
                    "symbol": symbol,
                    "document_id": document_id,
                    "source_url": doc.get("source_url"),
                    "segment_count": len(segments),
                    "segment_manifest_sha256": doc.get("segment_manifest_sha256"),
                    "prompt_sha256": prompt["prompt_sha256"],
                    "prompt_envelope": prompt,
                }
            )
            family_counts[family]+=1
            if family_counts[family]>=PER_FAMILY:
                break

    expected=sum(min(PER_FAMILY,family_counts.get(family,0)) for family in FAMILIES)
    if len(selected)!=expected:
        raise AlphaContractError("SS002 L001 pilot selection accounting mismatch")

    output={
        "schema_version":1,
        "selection_id":SELECTION_ID,
        "classification":"FROZEN_LLM_EXTRACTION_PILOT_SELECTION_NOT_ALPHA",
        "source_p2_census_sha256":EXPECTED_P2_SHA,
        "source_d3_corpus_sha256":EXPECTED_D3_SHA,
        "families":list(FAMILIES),
        "per_family_cap":PER_FAMILY,
        "family_counts":dict(sorted(family_counts.items())),
        "selected_document_count":len(selected),
        "rows":selected,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    output["selection_sha256"]=digest(output)
    return output
