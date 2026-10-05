from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_llm_contract import build_prompt_envelope

SELECTION_ID = "HG004-D001-P1-v1"
EXPECTED_HG003_L002_ID = "HG003-L002-v1"
EXPECTED_HG003_L002_SHA = "ebe3b8f666a83b18695eca69c649ab6c66d721f157ebe6ed0d61e71ef4f937ea"
EXPECTED_P2_ID = "SS002-D001-P2-v1"
EXPECTED_P2_SHA = "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"
EXPECTED_D3_ID = "SS002-D003-v1"
EXPECTED_D3_SHA = "92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce"

EXPECTED_SYMBOLS = {
    "ANANTRAJ",
    "AXITA",
    "DATAMATICS",
    "DEVX",
    "FCL",
    "INOXGREEN",
    "NPST",
    "SAMBHV",
    "SANDESH",
    "SUVIDHAA",
    "TREL",
}
EXPECTED_CLUSTER_COUNT = 11
EXPECTED_EVENT_LINK_COUNT = 20
EXPECTED_DOCUMENT_COUNT = 19

ELIGIBLE_COMPANY_STATES = {
    "ACTIVE_DIRECT_CATALYST",
    "PROCEDURAL_DIRECT_REVIEW",
}
ELIGIBLE_STAGE_GROUPS = {
    "ACTIVE_FORWARD_STAGE",
    "PROCEDURAL_STAGE",
}


def _require_research_only(payload: dict[str, Any], label: str) -> None:
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if payload.get(field) is not False:
            raise AlphaContractError(f"HG004 requires {label} {field}=false")


def _validate_inputs(
    hg003_l002: dict[str, Any],
    p2: dict[str, Any],
    d3: dict[str, Any],
) -> None:
    if (
        hg003_l002.get("synthesis_id") != EXPECTED_HG003_L002_ID
        or hg003_l002.get("synthesis_sha256") != EXPECTED_HG003_L002_SHA
    ):
        raise AlphaContractError("HG004 HG003-L002 source mismatch")
    if (
        p2.get("census_id") != EXPECTED_P2_ID
        or p2.get("census_sha256") != EXPECTED_P2_SHA
    ):
        raise AlphaContractError("HG004 P2 source mismatch")
    if (
        d3.get("corpus_id") != EXPECTED_D3_ID
        or d3.get("corpus_sha256") != EXPECTED_D3_SHA
    ):
        raise AlphaContractError("HG004 D3 source mismatch")
    _require_research_only(hg003_l002, "HG003-L002")
    _require_research_only(p2, "P2")
    _require_research_only(d3, "D3")


def _eligible_clusters(
    hg003_l002: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = hg003_l002.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("HG004 HG003-L002 rows unavailable")

    clusters: list[dict[str, Any]] = []
    symbols: set[str] = set()
    for company in rows:
        if not isinstance(company, dict):
            raise TypeError("HG004 HG003-L002 company rows must be objects")
        state = str(company.get("company_catalyst_state") or "")
        if state not in ELIGIBLE_COMPANY_STATES:
            continue
        symbol = str(company.get("symbol") or "").upper()
        if not symbol:
            raise AlphaContractError("HG004 eligible company lacks symbol")
        symbols.add(symbol)
        company_clusters = company.get("clusters")
        if not isinstance(company_clusters, list):
            raise AlphaContractError(f"{symbol}: clusters unavailable")
        for cluster in company_clusters:
            if not isinstance(cluster, dict):
                raise TypeError("HG004 cluster must be object")
            if cluster.get("relevance_group") != "CURRENT_ECONOMIC_RELEVANCE":
                continue
            if cluster.get("stage_group") not in ELIGIBLE_STAGE_GROUPS:
                continue
            member_thread_ids = cluster.get("member_thread_ids")
            if not isinstance(member_thread_ids, list) or not member_thread_ids:
                raise AlphaContractError(f"{symbol}: cluster member threads unavailable")
            categories = []
            for thread_id in member_thread_ids:
                raw = str(thread_id)
                prefix = f"{symbol}::"
                if not raw.startswith(prefix) or len(raw) <= len(prefix):
                    raise AlphaContractError(f"{symbol}: invalid member thread id {raw}")
                categories.append(raw[len(prefix):])
            clusters.append(
                {
                    "symbol": symbol,
                    "company_catalyst_state": state,
                    "semantic_cluster": str(cluster.get("semantic_cluster") or ""),
                    "latest_stage_group": str(cluster.get("stage_group") or ""),
                    "latest_transaction_stage": str(
                        cluster.get("latest_transaction_stage") or ""
                    ),
                    "latest_thread_id": str(cluster.get("latest_thread_id") or ""),
                    "member_thread_ids": sorted(str(v) for v in member_thread_ids),
                    "upstream_categories": sorted(set(categories)),
                }
            )

    if symbols != EXPECTED_SYMBOLS:
        raise AlphaContractError(
            f"HG004 expected frozen 11-symbol set, observed {sorted(symbols)}"
        )
    if len(clusters) != EXPECTED_CLUSTER_COUNT:
        raise AlphaContractError(
            f"HG004 expected {EXPECTED_CLUSTER_COUNT} clusters, observed {len(clusters)}"
        )
    return sorted(
        clusters,
        key=lambda row: (row["symbol"], row["semantic_cluster"]),
    )


def _event_index(p2: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = p2.get("events")
    if not isinstance(rows, list):
        raise AlphaContractError("HG004 P2 events unavailable")
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG004 P2 event rows must be objects")
        event_id = str(row.get("announcement_id") or "")
        if not event_id:
            raise AlphaContractError("HG004 P2 event lacks announcement_id")
        if event_id in seen_ids:
            raise AlphaContractError(f"HG004 duplicate P2 event id: {event_id}")
        seen_ids.add(event_id)
        if row.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        symbol = str(row.get("symbol") or "").upper()
        if symbol:
            result[symbol].append(row)
    return result


def _manifest_indexes(
    d3: dict[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    rows = d3.get("documents")
    if not isinstance(rows, list) or len(rows) != d3.get("document_count"):
        raise AlphaContractError("HG004 D3 document manifest unavailable")
    by_id: dict[str, dict[str, Any]] = {}
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG004 D3 manifest row must be object")
        document_id = str(row.get("document_id") or "")
        if not document_id or document_id in by_id:
            raise AlphaContractError("HG004 D3 document IDs must be unique")
        by_id[document_id] = row
        event_ids = row.get("event_ids")
        if not isinstance(event_ids, list):
            raise AlphaContractError(f"{document_id}: event_ids unavailable")
        for event_id in event_ids:
            by_event[str(event_id)].append(row)
    return by_id, by_event


def _record_index(
    manifest_by_id: dict[str, dict[str, Any]],
    document_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for row in document_records:
        if not isinstance(row, dict):
            raise TypeError("HG004 document records must be objects")
        document_id = str(row.get("document_id") or "")
        if not document_id or document_id not in manifest_by_id:
            raise AlphaContractError("HG004 document record identity mismatch")
        if document_id in records:
            raise AlphaContractError("HG004 duplicate document record")
        records[document_id] = row
    if set(records) != set(manifest_by_id):
        raise AlphaContractError("HG004 document records do not cover D3 manifest")
    return records


def _eligible_events_for_cluster(
    *,
    cluster: dict[str, Any],
    events_by_symbol: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    symbol = cluster["symbol"]
    categories = set(cluster["upstream_categories"])
    rows = []
    for event in events_by_symbol.get(symbol, []):
        event_categories = event.get("special_situation_categories")
        if not isinstance(event_categories, list):
            continue
        if not categories.intersection(str(v) for v in event_categories):
            continue
        rows.append(event)
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("exchange_published_at_utc") or ""),
            str(row.get("announcement_id") or ""),
        ),
    )


def select_hg004_detailed_terms(
    hg003_l002: dict[str, Any],
    p2: dict[str, Any],
    d3: dict[str, Any],
    document_records: list[dict[str, Any]],
) -> dict[str, Any]:
    _validate_inputs(hg003_l002, p2, d3)
    clusters = _eligible_clusters(hg003_l002)
    events_by_symbol = _event_index(p2)
    manifest_by_id, manifests_by_event = _manifest_indexes(d3)
    records = _record_index(manifest_by_id, document_records)

    event_links: list[dict[str, Any]] = []
    prompt_accumulator: dict[str, dict[str, Any]] = {}
    cluster_counts: Counter[str] = Counter()

    for cluster in clusters:
        rows = _eligible_events_for_cluster(
            cluster=cluster,
            events_by_symbol=events_by_symbol,
        )
        if not rows:
            raise AlphaContractError(
                f"{cluster['symbol']}::{cluster['semantic_cluster']}: no P2 events"
            )

        for event in rows:
            event_id = str(event["announcement_id"])
            ready_manifests = sorted(
                (
                    manifest
                    for manifest in manifests_by_event.get(event_id, [])
                    if manifest.get("extraction_state") == "READY"
                ),
                key=lambda row: str(row.get("document_id") or ""),
            )
            if not ready_manifests:
                raise AlphaContractError(
                    f"{event_id}: no TEXT_READY document for HG004 event"
                )
            selected_manifest = ready_manifests[0]
            document_id = str(selected_manifest["document_id"])
            record = records[document_id]
            if record.get("extraction_state") != "READY":
                raise AlphaContractError(
                    f"{document_id}: selected document record is not READY"
                )
            segments = record.get("segments")
            if not isinstance(segments, list) or not segments:
                raise AlphaContractError(
                    f"{document_id}: selected READY document has no segments"
                )

            event_links.append(
                {
                    "symbol": cluster["symbol"],
                    "company_catalyst_state": cluster["company_catalyst_state"],
                    "semantic_cluster": cluster["semantic_cluster"],
                    "upstream_categories": cluster["upstream_categories"],
                    "announcement_id": event_id,
                    "exchange_published_at_utc": event.get(
                        "exchange_published_at_utc"
                    ),
                    "document_id": document_id,
                    "source_url": selected_manifest.get("source_url"),
                }
            )
            cluster_counts[
                f"{cluster['symbol']}::{cluster['semantic_cluster']}"
            ] += 1

            item = prompt_accumulator.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "source_url": str(selected_manifest.get("source_url") or ""),
                    "event_ids": set(),
                    "symbols": set(),
                    "category_hints": set(),
                    "segment_manifest_sha256": str(
                        selected_manifest.get("segment_manifest_sha256") or ""
                    ),
                    "segments": segments,
                    "semantic_clusters": set(),
                    "company_catalyst_states": set(),
                },
            )
            item["event_ids"].add(event_id)
            item["symbols"].add(cluster["symbol"])
            item["category_hints"].update(cluster["upstream_categories"])
            item["semantic_clusters"].add(cluster["semantic_cluster"])
            item["company_catalyst_states"].add(
                cluster["company_catalyst_state"]
            )

    if len(event_links) != EXPECTED_EVENT_LINK_COUNT:
        raise AlphaContractError(
            f"HG004 expected {EXPECTED_EVENT_LINK_COUNT} event links, observed {len(event_links)}"
        )
    if len(prompt_accumulator) != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError(
            f"HG004 expected {EXPECTED_DOCUMENT_COUNT} unique docs, observed {len(prompt_accumulator)}"
        )
    if len(cluster_counts) != EXPECTED_CLUSTER_COUNT or any(
        count <= 0 for count in cluster_counts.values()
    ):
        raise AlphaContractError("HG004 cluster event accounting mismatch")

    prompts = []
    for document_id, item in sorted(prompt_accumulator.items()):
        prompt = build_prompt_envelope(
            document_id=document_id,
            source_url=item["source_url"],
            event_ids=sorted(item["event_ids"]),
            symbols=sorted(item["symbols"]),
            category_hints=sorted(item["category_hints"]),
            segments=item["segments"],
            segment_manifest_sha256=item["segment_manifest_sha256"],
        )
        prompts.append(
            {
                "document_id": document_id,
                "source_url": item["source_url"],
                "event_ids": sorted(item["event_ids"]),
                "symbols": sorted(item["symbols"]),
                "category_hints": sorted(item["category_hints"]),
                "semantic_clusters": sorted(item["semantic_clusters"]),
                "company_catalyst_states": sorted(
                    item["company_catalyst_states"]
                ),
                "segment_count": len(item["segments"]),
                "segment_manifest_sha256": item["segment_manifest_sha256"],
                "prompt_sha256": prompt["prompt_sha256"],
                "prompt_envelope": prompt,
            }
        )

    threshold_passes = {
        "exact_11_symbols": {
            row["symbol"] for row in event_links
        } == EXPECTED_SYMBOLS,
        "exact_11_clusters": len(cluster_counts) == EXPECTED_CLUSTER_COUNT,
        "exact_20_event_links": len(event_links) == EXPECTED_EVENT_LINK_COUNT,
        "all_event_links_text_ready": all(
            row["document_id"] in prompt_accumulator for row in event_links
        ),
        "exact_19_unique_documents": len(prompts) == EXPECTED_DOCUMENT_COUNT,
        "every_cluster_has_document": all(
            count > 0 for count in cluster_counts.values()
        ),
        "all_prompts_materialized": all(
            row["prompt_envelope"] is not None for row in prompts
        ),
    }

    output = {
        "schema_version": 1,
        "selection_id": SELECTION_ID,
        "classification": "HG002_ACTIVE_PROCEDURAL_DETAILED_TERM_SELECTION_NOT_ALPHA",
        "source_hg003_l002_sha256": EXPECTED_HG003_L002_SHA,
        "source_p2_census_sha256": EXPECTED_P2_SHA,
        "source_d3_corpus_sha256": EXPECTED_D3_SHA,
        "symbol_count": len(EXPECTED_SYMBOLS),
        "semantic_cluster_count": len(cluster_counts),
        "event_link_count": len(event_links),
        "unique_document_count": len(prompts),
        "cluster_event_counts": dict(sorted(cluster_counts.items())),
        "event_links": event_links,
        "prompts": prompts,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_detailed_l001": all(
            threshold_passes.values()
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["selection_sha256"] = digest(output)
    return output
