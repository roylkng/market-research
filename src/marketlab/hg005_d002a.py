from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcements import normalize_announcement_payload
from marketlab.events import sha256_bytes
from marketlab.ss002_attachments import detect_document_family
from marketlab.ss002_special_situations import approved_attachment_url
from marketlab.ss002_text import extract_document_text

CORPUS_ID = "HG005-D002A-v1"
MANIFEST_ID = "HG005-D002-SOURCE-MANIFEST-v1"
EXPECTED_SOURCE_COUNT = 19
EXPECTED_SYMBOLS = {"ANANTRAJ", "DEVX", "INOXGREEN", "NPST", "SAMBHV"}
MANDATORY_SOURCE_IDS = {
    "ANANTRAJ_SCHEME_BOARD_OUTCOME",
    "DEVX_PREF_MONITORING_Q1FY27",
    "INOXGREEN_WWIL_PLAN_UPDATE",
    "NPST_Q1FY27_MONITORING",
    "SAMBHV_WARRANT_EGM_NOTICE",
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def validate_source_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1:
        raise AlphaContractError("HG005 D002A source manifest schema_version must equal 1")
    if manifest.get("manifest_id") != MANIFEST_ID:
        raise AlphaContractError("HG005 D002A manifest_id mismatch")
    if set(manifest.get("symbols") or []) != EXPECTED_SYMBOLS:
        raise AlphaContractError("HG005 D002A symbol set mismatch")
    for field in (
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if manifest.get(field) is not False:
            raise AlphaContractError(f"HG005 D002A manifest requires {field}=false")

    hosts = manifest.get("allowed_direct_hosts")
    if not isinstance(hosts, list) or not hosts:
        raise AlphaContractError("HG005 D002A allowed host list unavailable")
    allowed_hosts = {str(host).casefold() for host in hosts}

    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError(
            f"HG005 D002A expected {EXPECTED_SOURCE_COUNT} source rows"
        )

    seen: set[str] = set()
    for row in sources:
        if not isinstance(row, dict):
            raise TypeError("HG005 D002A source row must be an object")
        source_id = _clean(row.get("source_id"))
        symbol = _clean(row.get("symbol")).upper()
        mode = _clean(row.get("mode"))
        if not source_id or source_id in seen:
            raise AlphaContractError("HG005 D002A source IDs must be unique")
        seen.add(source_id)
        if symbol not in EXPECTED_SYMBOLS:
            raise AlphaContractError(f"{source_id}: unsupported symbol {symbol}")
        groups = row.get("required_fact_groups")
        if not isinstance(groups, list) or not groups or not all(
            isinstance(value, str) and value for value in groups
        ):
            raise AlphaContractError(f"{source_id}: required_fact_groups unavailable")

        if mode == "DIRECT_URL":
            url = _clean(row.get("url"))
            parsed = urlparse(url)
            if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in allowed_hosts:
                raise AlphaContractError(f"{source_id}: direct URL violates host policy")
        elif mode == "NSE_ANNOUNCEMENT_DISCOVERY":
            discovery = row.get("discovery")
            if not isinstance(discovery, dict):
                raise AlphaContractError(f"{source_id}: discovery spec unavailable")
            try:
                start = date.fromisoformat(
                    date.fromisoformat(
                        "-".join(reversed(_clean(discovery.get("from_date")).split("-")))
                    ).isoformat()
                )
                end = date.fromisoformat(
                    date.fromisoformat(
                        "-".join(reversed(_clean(discovery.get("to_date")).split("-")))
                    ).isoformat()
                )
            except ValueError as exc:
                raise AlphaContractError(
                    f"{source_id}: discovery dates must be DD-MM-YYYY"
                ) from exc
            if start > end:
                raise AlphaContractError(f"{source_id}: discovery date window reversed")
            tokens = discovery.get("desc_tokens")
            if not isinstance(tokens, list) or not tokens or not all(
                isinstance(value, str) and value.strip() for value in tokens
            ):
                raise AlphaContractError(f"{source_id}: discovery tokens unavailable")
        else:
            raise AlphaContractError(f"{source_id}: unsupported acquisition mode {mode}")

    if not MANDATORY_SOURCE_IDS.issubset(seen):
        raise AlphaContractError("HG005 D002A mandatory source IDs are missing")
    return sources


def resolve_discovery_attachment(
    *,
    source: dict[str, Any],
    payload: object,
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    symbol = str(source["symbol"]).upper()
    discovery = source["discovery"]
    raw_from = str(discovery["from_date"])
    raw_to = str(discovery["to_date"])
    start = date.fromisoformat("-".join(reversed(raw_from.split("-"))))
    end = date.fromisoformat("-".join(reversed(raw_to.split("-"))))
    rows = normalize_announcement_payload(
        payload,
        requested_start=start,
        requested_end=end,
    )
    wanted_tokens = [str(token).casefold() for token in discovery["desc_tokens"]]
    matches = []
    for row in rows:
        if str(row.get("symbol") or "").upper() != symbol:
            continue
        haystack = (
            f"{_clean(row.get('desc'))} {_clean(row.get('attchmntText'))}"
        ).casefold()
        if all(token in haystack for token in wanted_tokens):
            url = approved_attachment_url(row.get("attchmntFile"))
            if url is not None:
                matches.append((row, url))
    if len(matches) != 1:
        raise AlphaContractError(
            f"{source_id}: expected one discovery match, observed {len(matches)}"
        )
    row, url = matches[0]
    return {
        "announcement_id": row["announcement_id"],
        "exchange_published_at_utc": row["exchange_published_at_utc"],
        "desc": row["desc"],
        "attchmntText": row["attchmntText"],
        "resolved_url": url,
    }


def source_evidence(
    *,
    source: dict[str, Any],
    resolved_url: str | None,
    raw: bytes | None,
    discovery_raw_sha256: str | None = None,
    discovery_match: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    if raw is None:
        if not error:
            raise AlphaContractError(f"{source_id}: failed source requires error")
        return {
            "source_id": source_id,
            "symbol": source["symbol"],
            "mode": source["mode"],
            "source_type": source["source_type"],
            "required_fact_groups": source["required_fact_groups"],
            "status": "SOURCE_FAILED",
            "resolved_url": resolved_url,
            "raw_sha256": None,
            "raw_byte_count": None,
            "document_family": None,
            "text_state": "UNAVAILABLE",
            "segment_manifest_sha256": None,
            "segments": [],
            "discovery_raw_sha256": discovery_raw_sha256,
            "discovery_match": discovery_match,
            "error": error,
        }

    if not resolved_url:
        raise AlphaContractError(f"{source_id}: READY source requires URL")

    sha = sha256_bytes(raw)
    family = detect_document_family(raw, resolved_url)
    extraction = extract_document_text(
        document_id=sha,
        raw=raw,
        d002_family=family,
        source_url=resolved_url,
    )
    segments = extraction.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError(f"{source_id}: text segments unavailable")
    for segment in segments:
        text = segment.get("text")
        text_sha = segment.get("text_sha256")
        if not isinstance(text, str) or sha256_bytes(text.encode("utf-8")) != text_sha:
            raise AlphaContractError(f"{source_id}: segment text SHA mismatch")

    text_state = (
        "READY_TEXT"
        if extraction.get("extraction_state") == "READY"
        else str(extraction.get("extraction_state") or "TEXT_FAILED")
    )
    return {
        "source_id": source_id,
        "symbol": source["symbol"],
        "mode": source["mode"],
        "source_type": source["source_type"],
        "required_fact_groups": source["required_fact_groups"],
        "status": "READY_SOURCE",
        "resolved_url": resolved_url,
        "raw_sha256": sha,
        "raw_byte_count": len(raw),
        "document_family": family,
        "text_state": text_state,
        "segment_manifest_sha256": extraction.get("segment_manifest_sha256"),
        "segments": segments,
        "discovery_raw_sha256": discovery_raw_sha256,
        "discovery_match": discovery_match,
        "error": None,
    }


def build_source_corpus(
    *,
    manifest: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    sources = validate_source_manifest(manifest)
    expected = {str(row["source_id"]) for row in sources}
    by_id: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            raise TypeError("HG005 D002A evidence row must be an object")
        source_id = str(row.get("source_id") or "")
        if not source_id or source_id in by_id:
            raise AlphaContractError("HG005 D002A evidence source IDs must be unique")
        by_id[source_id] = row
    if set(by_id) != expected:
        raise AlphaContractError("HG005 D002A evidence accounting mismatch")

    ready_sources = [
        row for row in evidence_rows if row.get("status") == "READY_SOURCE"
    ]
    ready_text = [
        row for row in evidence_rows if row.get("text_state") == "READY_TEXT"
    ]
    mandatory_text_ready = all(
        by_id[source_id].get("text_state") == "READY_TEXT"
        for source_id in MANDATORY_SOURCE_IDS
    )
    resolved_ratio = len(ready_sources) / EXPECTED_SOURCE_COUNT
    text_ratio = len(ready_text) / max(len(ready_sources), 1)

    symbol_counts: Counter[str] = Counter()
    fact_group_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    total_segments = 0
    for row in evidence_rows:
        if row.get("status") == "READY_SOURCE":
            symbol_counts[str(row["symbol"])] += 1
            family_counts[str(row.get("document_family") or "")] += 1
            for group in row.get("required_fact_groups") or []:
                fact_group_counts[str(group)] += 1
            total_segments += len(row.get("segments") or [])
        else:
            failure_counts[str(row.get("error") or "UNKNOWN")] += 1

    gates = {
        "exact_19_source_accounting": len(evidence_rows) == EXPECTED_SOURCE_COUNT,
        "all_mandatory_anchor_sources_ready_text": mandatory_text_ready,
        "minimum_18_of_19_sources_resolved": len(ready_sources) >= 18,
        "minimum_90pct_resolved_sources_text_ready": text_ratio >= 0.90,
        "deterministic_segment_hashes": all(
            all(
                sha256_bytes(str(segment["text"]).encode("utf-8"))
                == segment["text_sha256"]
                for segment in row.get("segments") or []
            )
            for row in ready_text
        ),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "OFFICIAL_PAYOFF_ENRICHMENT_SOURCE_CORPUS_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "manifest_id": MANIFEST_ID,
        "manifest_sha256": digest(manifest),
        "source_count": EXPECTED_SOURCE_COUNT,
        "ready_source_count": len(ready_sources),
        "ready_source_ratio": resolved_ratio,
        "ready_text_count": len(ready_text),
        "ready_text_ratio_of_resolved": text_ratio,
        "mandatory_text_ready": mandatory_text_ready,
        "symbol_ready_source_counts": dict(sorted(symbol_counts.items())),
        "fact_group_source_counts": dict(sorted(fact_group_counts.items())),
        "document_family_counts": dict(sorted(family_counts.items())),
        "failure_reason_counts": dict(sorted(failure_counts.items())),
        "segment_count": total_segments,
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_d002b": all(gates.values()),
        "sources": sorted(evidence_rows, key=lambda row: row["source_id"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "llm_inference_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
