from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.ss002_text import seal_extraction_row

CORPUS_ID = "HG006-D001B-v1"
EXPECTED_D001A_ID = "HG006-D001A-P1-v1"


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def document_requests(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    if corpus.get("corpus_id") != EXPECTED_D001A_ID:
        raise AlphaContractError("HG006 D001B requires passed D001A-P1 corpus")
    if corpus.get("feasibility_pass") is not True:
        raise AlphaContractError("HG006 D001B requires feasible D001A corpus")
    for field in (
        "historical_terminal_labels_opened",
        "completion_probabilities_assigned",
        "expected_returns_calculated",
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if corpus.get(field) is not False:
            raise AlphaContractError(f"HG006 D001B requires D001A {field}=false")

    rows = corpus.get("documents")
    if not isinstance(rows, list):
        raise AlphaContractError("HG006 D001B D001A documents unavailable")

    grouped: dict[str, dict[str, set]] = defaultdict(
        lambda: {
            "source_urls": set(),
            "shards": set(),
            "families": set(),
            "event_ids": set(),
            "chronology_ids": set(),
            "symbols": set(),
            "document_families": set(),
        }
    )
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "READY":
            continue
        document_id = _clean(row.get("document_id"))
        source_url = _clean(row.get("source_url"))
        family = _clean(row.get("document_family"))
        shard_id = row.get("shard_id")
        if (
            len(document_id) != 64
            or not source_url
            or not family
            or not isinstance(shard_id, int)
            or isinstance(shard_id, bool)
        ):
            raise AlphaContractError("HG006 D001B READY document row incomplete")
        item = grouped[document_id]
        item["source_urls"].add(source_url)
        item["shards"].add(shard_id)
        item["document_families"].add(family)
        item["families"].update(str(v) for v in row.get("families", []))
        item["event_ids"].update(str(v) for v in row.get("event_ids", []))
        item["chronology_ids"].update(
            str(v) for v in row.get("chronology_ids", [])
        )
        item["symbols"].update(str(v) for v in row.get("symbols", []))

    expected_count = corpus.get("unique_document_id_count")
    if not isinstance(expected_count, int) or len(grouped) != expected_count:
        raise AlphaContractError(
            "HG006 D001B unique document accounting mismatch"
        )

    requests = []
    for document_id, item in sorted(grouped.items()):
        if len(item["document_families"]) != 1:
            raise AlphaContractError(
                f"{document_id}: conflicting document-family semantics"
            )
        requests.append(
            {
                "document_id": document_id,
                "owner_shard": min(item["shards"]),
                "available_shards": sorted(item["shards"]),
                "source_urls": sorted(item["source_urls"]),
                "d002_family": next(iter(item["document_families"])),
                "families": sorted(item["families"]),
                "event_ids": sorted(item["event_ids"]),
                "chronology_ids": sorted(item["chronology_ids"]),
                "symbols": sorted(item["symbols"]),
            }
        )
    return requests


def extraction_index_row(
    extraction: dict[str, Any],
    *,
    request: dict[str, Any],
    text_artifact_path: str,
) -> dict[str, Any]:
    if extraction.get("document_id") != request.get("document_id"):
        raise AlphaContractError("HG006 D001B extraction document mismatch")
    segments = extraction.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("HG006 D001B extraction segments unavailable")

    expected_manifest = seal_extraction_row(
        {
            key: value
            for key, value in extraction.items()
            if key != "segment_manifest_sha256"
        }
    )["segment_manifest_sha256"]
    if extraction.get("segment_manifest_sha256") != expected_manifest:
        raise AlphaContractError("HG006 D001B segment manifest SHA mismatch")

    segment_ids = [str(row.get("segment_id") or "") for row in segments]
    if any(not value for value in segment_ids):
        raise AlphaContractError("HG006 D001B empty segment ID")
    if len(segment_ids) != len(set(segment_ids)):
        raise AlphaContractError("HG006 D001B duplicate segment ID within document")

    state = str(extraction.get("extraction_state") or "")
    if state == "READY" and not segments:
        raise AlphaContractError("HG006 D001B READY document needs segments")
    if state != "READY" and segments:
        raise AlphaContractError("HG006 D001B non-READY document cannot carry segments")

    return {
        "document_id": request["document_id"],
        "owner_shard": request["owner_shard"],
        "available_shards": request["available_shards"],
        "source_urls": request["source_urls"],
        "d002_family": request["d002_family"],
        "families": request["families"],
        "event_ids": request["event_ids"],
        "chronology_ids": request["chronology_ids"],
        "symbols": request["symbols"],
        "hash_reproduced": bool(extraction.get("hash_reproduced")),
        "extraction_state": state,
        "segment_manifest_sha256": extraction.get("segment_manifest_sha256"),
        "segment_count": len(segments),
        "segment_ids": segment_ids,
        "details": extraction.get("details") or {},
        "text_artifact_path": text_artifact_path,
    }


def build_historical_text_corpus(
    *,
    d001a_corpus: dict[str, Any],
    index_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    requests = document_requests(d001a_corpus)
    expected = {row["document_id"]: row for row in requests}
    by_id: dict[str, dict[str, Any]] = {}
    for row in index_rows:
        if not isinstance(row, dict):
            raise TypeError("HG006 D001B index row must be object")
        document_id = _clean(row.get("document_id"))
        if document_id not in expected or document_id in by_id:
            raise AlphaContractError("HG006 D001B index document mismatch")
        if row.get("owner_shard") != expected[document_id]["owner_shard"]:
            raise AlphaContractError("HG006 D001B owner-shard mismatch")
        by_id[document_id] = row
    if set(by_id) != set(expected):
        raise AlphaContractError("HG006 D001B incomplete document accounting")

    state_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    reproduced = 0
    ready = 0
    pdf_reproduced = 0
    pdf_ready = 0
    segment_count = 0
    segment_ids: set[str] = set()

    for request in requests:
        row = by_id[request["document_id"]]
        state = str(row.get("extraction_state") or "UNKNOWN")
        family = request["d002_family"]
        state_counts[state] += 1
        family_counts[family] += 1

        if row.get("hash_reproduced") is True:
            reproduced += 1
            if family == "PDF":
                pdf_reproduced += 1
        if state == "READY":
            ready += 1
            if family == "PDF":
                pdf_ready += 1

        ids = row.get("segment_ids")
        if not isinstance(ids, list) or not all(isinstance(v, str) for v in ids):
            raise AlphaContractError("HG006 D001B segment index malformed")
        if len(ids) != len(set(ids)):
            raise AlphaContractError("HG006 D001B duplicate segment ID in index")
        overlap = segment_ids.intersection(ids)
        if overlap:
            raise AlphaContractError("HG006 D001B segment IDs not globally unique")
        segment_ids.update(ids)
        segment_count += len(ids)

    document_count = len(requests)
    reproduced_ratio = reproduced / document_count if document_count else 1.0
    text_ready_ratio = ready / reproduced if reproduced else 0.0
    pdf_ready_ratio = pdf_ready / pdf_reproduced if pdf_reproduced else 1.0

    gates = {
        "complete_document_accounting": len(index_rows) == document_count,
        "minimum_hash_reproduction_99pct": reproduced_ratio >= 0.99,
        "minimum_text_ready_80pct": text_ready_ratio >= 0.80,
        "minimum_pdf_text_ready_80pct": pdf_ready_ratio >= 0.80,
        "deterministic_global_segment_identity": (
            segment_count == len(segment_ids)
        ),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "DETERMINISTIC_HISTORICAL_PRIORITY_FAMILY_TEXT_CORPUS_NOT_PROBABILITY",
        "captured_at_utc": captured_at_utc,
        "source_d001a_corpus_sha256": d001a_corpus.get("corpus_sha256"),
        "selected_families": d001a_corpus.get("selected_families"),
        "document_count": document_count,
        "hash_reproduced_count": reproduced,
        "hash_reproduced_ratio": reproduced_ratio,
        "text_ready_document_count": ready,
        "text_ready_ratio_of_reproduced": text_ready_ratio,
        "pdf_reproduced_count": pdf_reproduced,
        "pdf_text_ready_count": pdf_ready,
        "pdf_text_ready_ratio": pdf_ready_ratio,
        "segment_count": segment_count,
        "extraction_state_counts": dict(sorted(state_counts.items())),
        "document_family_counts": dict(sorted(family_counts.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_hg006_l001": all(gates.values()),
        "documents": sorted(index_rows, key=lambda row: row["document_id"]),
        "historical_terminal_labels_opened": False,
        "completion_probabilities_assigned": False,
        "expected_returns_calculated": False,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "llm_inference_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
