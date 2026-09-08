from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from marketlab.claims import ManagementClaim
from marketlab.h003_outcomes import (
    CLAIM_AUDIT_SHA256,
    EXPECTED_ACCEPTED_CLAIMS,
    OUTCOME_RULE_ID,
    OUTCOME_RULE_SHA256,
    REVIEW_LEDGER_SHA256,
    SOURCE_BUNDLE_SHA256,
    SOURCE_CUTOFF_UTC,
    H003OutcomeError,
    _canonical_hash,
    _parse_timestamp,
    build_blind_outcome_payload,
    build_source_passages,
    load_and_validate_outcome_rule,
    select_evidence_passages,
)
from marketlab.h003_review import load_complete_candidate_corpus

FORBIDDEN_MARKET_PHRASES = (
    "share price",
    "stock price",
    "price target",
    "nifty",
    "sensex",
    "market capitalization",
    "market capitalisation",
    "market cap",
    "total shareholder return",
    "total return",
    "stock return",
    "share return",
)
LEGAL_SUFFIX_PATTERN = re.compile(
    r"\s+(?:limited|ltd\.?|private limited|pvt\.? ltd\.?)$", re.IGNORECASE
)
CANDIDATE_LOCATOR_PATTERN = re.compile(r"(?:^|;)candidate=([0-9a-f]{64})(?:;|$)")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_frozen_ledger(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    declared = document.get("ledger_sha256")
    unsigned = dict(document)
    unsigned.pop("ledger_sha256", None)
    recomputed = _canonical_hash(unsigned)
    if declared != REVIEW_LEDGER_SHA256 or recomputed != REVIEW_LEDGER_SHA256:
        raise H003OutcomeError(
            f"frozen review ledger hash mismatch: declared={declared}, recomputed={recomputed}"
        )
    claims = document.get("accepted_claims")
    if not isinstance(claims, list) or len(claims) != EXPECTED_ACCEPTED_CLAIMS:
        raise H003OutcomeError("frozen accepted claim count changed")
    seen: set[str] = set()
    for payload in claims:
        claim = ManagementClaim(**payload)
        if claim.claim_id in seen:
            raise H003OutcomeError(f"duplicate frozen claim id: {claim.claim_id}")
        seen.add(claim.claim_id)
        if claim.claim_hash != claim.computed_hash():
            raise H003OutcomeError(f"frozen claim hash mismatch: {claim.claim_id}")
    return document


def load_claim_audit(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    declared = document.get("audit_sha256")
    unsigned = dict(document)
    unsigned.pop("audit_sha256", None)
    if declared != CLAIM_AUDIT_SHA256 or _canonical_hash(unsigned) != CLAIM_AUDIT_SHA256:
        raise H003OutcomeError("H003-A001 claim audit hash mismatch")
    if document.get("outcome_data_accessed") is not False:
        raise H003OutcomeError("claim audit unexpectedly accessed outcome data")
    return document


def load_universe(path: Path) -> dict[str, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    members = document.get("members")
    if not isinstance(members, list):
        raise H003OutcomeError("frozen universe members missing")
    by_symbol: dict[str, dict[str, Any]] = {}
    for row in members:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol or symbol in by_symbol:
            raise H003OutcomeError("invalid or duplicate universe symbol")
        by_symbol[symbol] = row
    return by_symbol


def redaction_terms(member: dict[str, Any], symbol: str) -> tuple[str, ...]:
    name = str(member.get("company_name") or "").strip()
    root = LEGAL_SUFFIX_PATTERN.sub("", name).strip()
    variants = {
        symbol,
        name,
        root,
        name.replace("Ltd.", "Limited"),
        name.replace("Ltd", "Limited"),
        root.replace("&", "and"),
        root.replace("and", "&"),
    }
    return tuple(sorted((item for item in variants if item), key=len, reverse=True))


def claim_candidate_id(claim: dict[str, Any]) -> str:
    match = CANDIDATE_LOCATOR_PATTERN.search(str(claim.get("source_locator") or ""))
    if match is None:
        raise H003OutcomeError(
            f"claim source locator lacks candidate identity: {claim.get('claim_id')}"
        )
    return match.group(1)


def load_report_and_records(report_path: Path) -> tuple[Any, list[dict[str, Any]]]:
    corpus = load_complete_candidate_corpus(report_path)
    if corpus.source_bundle_sha256 != SOURCE_BUNDLE_SHA256:
        raise H003OutcomeError("candidate report source bundle changed")
    document = json.loads(report_path.read_text(encoding="utf-8"))
    records = document.get("records")
    if not isinstance(records, list) or len(records) != 794:
        raise H003OutcomeError("candidate report must contain 794 source records")
    return corpus, records


def verified_source_text(store_root: Path, record: dict[str, Any]) -> str:
    relative = record.get("text_path")
    expected = record.get("text_sha256")
    if not isinstance(relative, str) or not isinstance(expected, str) or len(expected) != 64:
        raise H003OutcomeError(f"source text metadata missing: {record.get('source_id')}")
    path = store_root / relative
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise H003OutcomeError(f"source text missing: {path}") from exc
    actual = sha256_bytes(raw)
    if actual != expected:
        raise H003OutcomeError(
            f"source text SHA mismatch: source={record.get('source_id')} expected={expected} actual={actual}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise H003OutcomeError(f"source text is not UTF-8: {path}") from exc


def contains_forbidden_market_text(text: str) -> bool:
    lowered = text.casefold()
    return any(phrase in lowered for phrase in FORBIDDEN_MARKET_PHRASES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--claim-audit", type=Path, required=True)
    parser.add_argument("--outcome-rule", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--blind-out", type=Path, required=True)
    parser.add_argument("--binding-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()

    rule = load_and_validate_outcome_rule(args.outcome_rule)
    ledger = load_frozen_ledger(args.ledger)
    load_claim_audit(args.claim_audit)
    corpus, records = load_report_and_records(args.candidate_report)
    universe = load_universe(args.universe)

    cutoff = _parse_timestamp(SOURCE_CUTOFF_UTC, field="SOURCE_CUTOFF_UTC")
    records_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_by_source_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("status") != "TEXT_READY":
            raise H003OutcomeError(f"non-TEXT_READY source in complete report: {record.get('source_id')}")
        timestamp = _parse_timestamp(
            str(record.get("exchange_published_at_utc")),
            field="record.exchange_published_at_utc",
        )
        if timestamp > cutoff:
            raise H003OutcomeError(f"source exceeds frozen outcome cutoff: {record.get('source_id')}")
        source_id = str(record.get("source_id") or "")
        symbol = str(record.get("symbol") or "").upper()
        if source_id in record_by_source_id:
            raise H003OutcomeError(f"duplicate source id: {source_id}")
        record_by_source_id[source_id] = record
        records_by_symbol[symbol].append(record)
    for rows in records_by_symbol.values():
        rows.sort(
            key=lambda item: (
                _parse_timestamp(
                    str(item["exchange_published_at_utc"]),
                    field="record.exchange_published_at_utc",
                ),
                str(item["source_id"]),
            )
        )

    # Validate every referenced candidate and retain exact source timestamp.
    claim_rows = ledger["accepted_claims"]
    blind_packets: list[dict[str, Any]] = []
    binding_rows: list[dict[str, Any]] = []
    empty_packets = 0
    eligible_source_counts: list[int] = []
    selected_passage_counts: list[int] = []
    market_filtered_passages = 0
    selected_source_counter: Counter[str] = Counter()

    source_passage_cache: dict[str, tuple[Any, ...]] = {}
    for claim in sorted(claim_rows, key=lambda item: str(item["claim_id"])):
        symbol = str(claim["symbol"]).upper()
        member = universe.get(symbol)
        if member is None:
            raise H003OutcomeError(f"claim symbol not in frozen universe: {symbol}")
        candidate_id = claim_candidate_id(claim)
        candidate = corpus.candidates_by_id.get(candidate_id)
        if candidate is None:
            raise H003OutcomeError(f"claim candidate not in complete report: {candidate_id}")
        if candidate.symbol.upper() != symbol:
            raise H003OutcomeError(f"claim/candidate symbol mismatch: {claim['claim_id']}")
        original_publication = _parse_timestamp(
            candidate.exchange_published_at_utc,
            field="candidate.exchange_published_at_utc",
        )

        eligible = [
            row
            for row in records_by_symbol.get(symbol, [])
            if original_publication
            < _parse_timestamp(
                str(row["exchange_published_at_utc"]),
                field="record.exchange_published_at_utc",
            )
            <= cutoff
        ]
        eligible_source_counts.append(len(eligible))

        all_passages = []
        source_binding: dict[str, dict[str, Any]] = {}
        for index, record in enumerate(eligible, start=1):
            source_id = str(record["source_id"])
            alias = f"EVIDENCE_SOURCE_{index:03d}"
            source_binding[alias] = {
                "source_id": source_id,
                "symbol": symbol,
                "exchange_published_at_utc": record["exchange_published_at_utc"],
                "attachment_url": record["attachment_url"],
                "raw_sha256": record["raw_sha256"],
                "text_sha256": record["text_sha256"],
                "record_id": record["record_id"],
            }
            cache_key = source_id
            if cache_key not in source_passage_cache:
                text = verified_source_text(args.store_root, record)
                source_passage_cache[cache_key] = build_source_passages(
                    source_alias="__SOURCE_ALIAS__",
                    source_text_sha256=str(record["text_sha256"]),
                    exchange_published_at_utc=str(record["exchange_published_at_utc"]),
                    canonical_text=text,
                )
            for cached in source_passage_cache[cache_key]:
                rebuilt = type(cached)(
                    source_alias=alias,
                    source_text_sha256=cached.source_text_sha256,
                    exchange_published_at_utc=cached.exchange_published_at_utc,
                    page_number=cached.page_number,
                    line_start=cached.line_start,
                    line_end=cached.line_end,
                    text=cached.text,
                    passage_id=cached.passage_id,
                )
                if contains_forbidden_market_text(rebuilt.text):
                    market_filtered_passages += 1
                    continue
                all_passages.append(rebuilt)

        selected = select_evidence_passages(claim, all_passages)
        terms = redaction_terms(member, symbol)
        packet = build_blind_outcome_payload(claim, selected, redaction_terms=terms)
        packet_document = packet.to_dict()

        # Fail if the most explicit frozen identity strings survive the packet.
        rendered = json.dumps(packet_document, ensure_ascii=False).casefold()
        for forbidden in (symbol, str(member.get("company_name") or "")):
            forbidden = forbidden.strip().casefold()
            if forbidden and forbidden in rendered:
                raise H003OutcomeError(
                    f"explicit company identity survived blind packet: {claim['claim_id']}"
                )

        if not packet.evidence:
            empty_packets += 1
        selected_passage_counts.append(len(packet.evidence))
        for item in packet.evidence:
            selected_source_counter[item.source_alias] += 1
        blind_packets.append(packet_document)
        binding_rows.append(
            {
                "packet_id": packet.packet_id,
                "blind_payload_sha256": packet.payload_sha256,
                "claim_id": claim["claim_id"],
                "claim_hash": claim["claim_hash"],
                "symbol": symbol,
                "company_name": member.get("company_name"),
                "candidate_id": candidate_id,
                "original_source_id": candidate.source_id,
                "original_exchange_published_at_utc": candidate.exchange_published_at_utc,
                "eligible_source_count": len(eligible),
                "source_bindings": source_binding,
                "selected_passage_ids": [item.passage_id for item in packet.evidence],
            }
        )

    if len(blind_packets) != EXPECTED_ACCEPTED_CLAIMS:
        raise H003OutcomeError("blind packet coverage is incomplete")
    packet_ids = [row["packet_id"] for row in blind_packets]
    if len(packet_ids) != len(set(packet_ids)):
        raise H003OutcomeError("duplicate blind outcome packet id")

    blind_unsigned = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "review_ledger_sha256": REVIEW_LEDGER_SHA256,
        "claim_audit_sha256": CLAIM_AUDIT_SHA256,
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "source_cutoff_utc": SOURCE_CUTOFF_UTC,
        "packet_count": len(blind_packets),
        "packets": blind_packets,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    blind_document = {**blind_unsigned, "package_sha256": _canonical_hash(blind_unsigned)}

    binding_unsigned = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "packet_count": len(binding_rows),
        "bindings": binding_rows,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    binding_document = {
        **binding_unsigned,
        "binding_sha256": _canonical_hash(binding_unsigned),
    }

    histogram = Counter(selected_passage_counts)
    manifest_unsigned = {
        "schema_version": 1,
        "outcome_rule_id": OUTCOME_RULE_ID,
        "outcome_rule_sha256": OUTCOME_RULE_SHA256,
        "review_ledger_sha256": REVIEW_LEDGER_SHA256,
        "claim_audit_sha256": CLAIM_AUDIT_SHA256,
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "source_cutoff_utc": SOURCE_CUTOFF_UTC,
        "packet_count": len(blind_packets),
        "empty_packet_count": empty_packets,
        "claims_with_any_eligible_later_source": sum(count > 0 for count in eligible_source_counts),
        "claims_without_eligible_later_source": sum(count == 0 for count in eligible_source_counts),
        "eligible_source_count_min": min(eligible_source_counts),
        "eligible_source_count_max": max(eligible_source_counts),
        "selected_passage_count_min": min(selected_passage_counts),
        "selected_passage_count_max": max(selected_passage_counts),
        "selected_passage_count_histogram": {
            str(key): value for key, value in sorted(histogram.items())
        },
        "forbidden_market_passage_filter_count": market_filtered_passages,
        "blind_package_sha256": blind_document["package_sha256"],
        "binding_package_sha256": binding_document["binding_sha256"],
        "outcome_data_accessed": False,
        "market_outcomes_included": False,
        "live_capital_allowed": False,
    }
    manifest_document = {
        **manifest_unsigned,
        "manifest_sha256": _canonical_hash(manifest_unsigned),
    }

    for path, document in (
        (args.blind_out, blind_document),
        (args.binding_out, binding_document),
        (args.manifest_out, manifest_document),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(manifest_document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
