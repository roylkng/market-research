from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.h003_candidates import extract_pdf_pages
from marketlab.h003_review import (
    REVIEW_RULE_ID,
    REVIEW_RULE_SHA256,
    BlindReviewPayload,
    CandidateCorpus,
    ReviewDecision,
    build_blind_review_payload,
    build_review_decision,
    load_and_validate_review_rule,
    load_complete_candidate_corpus,
    mechanical_rejection,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


class ReviewPackageError(ValueError):
    pass


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _company_redaction_terms(company_name: str, symbol: str) -> tuple[str, ...]:
    terms = {symbol.strip(), company_name.strip()}
    base = re.sub(
        r"(?i)\s+(?:limited|ltd\.?|private limited|pvt\.?\s+ltd\.?)$",
        "",
        company_name.strip(),
    ).strip()
    if base:
        terms.add(base)
        terms.add(base + " Limited")
        terms.add(base + " Ltd")
        terms.add(base + " Ltd.")
    return tuple(sorted((term for term in terms if term), key=len, reverse=True))


def _load_company_names(path: Path) -> dict[str, str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewPackageError(f"could not read universe {path}: {exc}") from exc
    members = document.get("members") if isinstance(document, dict) else None
    if not isinstance(members, list):
        raise ReviewPackageError("universe members must be a list")
    names: dict[str, str] = {}
    for member in members:
        if not isinstance(member, dict):
            raise ReviewPackageError("universe member must be an object")
        symbol = str(member.get("symbol") or "").strip().upper()
        company_name = str(member.get("company_name") or "").strip()
        if not symbol or not company_name or symbol in names:
            raise ReviewPackageError(f"invalid/duplicate universe member: {symbol}")
        names[symbol] = company_name
    if len(names) != 100:
        raise ReviewPackageError(f"expected 100 universe names, found {len(names)}")
    return names


def _fetch_pdf(client: NSEClient, url: str, *, attempts: int) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.archive_bytes(url)
        except NSEAcquisitionError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(8.0, 0.75 * (2 ** (attempt - 1))))
    assert last_error is not None
    raise ReviewPackageError(f"could not re-fetch frozen candidate PDF: {last_error}") from last_error


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _payload_sort_key(payload: BlindReviewPayload) -> tuple[str, int, int, str]:
    return (
        payload.evidence_sha256,
        payload.page_number,
        payload.line_start,
        payload.candidate_id,
    )


def build_package(
    corpus: CandidateCorpus,
    *,
    company_names: dict[str, str],
    client: NSEClient,
    fetch_attempts: int,
) -> tuple[dict[str, Any], list[BlindReviewPayload], list[ReviewDecision]]:
    candidates_by_source: dict[str, list[Any]] = defaultdict(list)
    for candidate in corpus.candidates_by_id.values():
        candidates_by_source[candidate.source_id].append(candidate)

    payloads: list[BlindReviewPayload] = []
    mechanical_decisions: list[ReviewDecision] = []
    fetched_source_count = 0
    for source_index, source_id in enumerate(sorted(candidates_by_source), start=1):
        candidates = sorted(
            candidates_by_source[source_id],
            key=lambda item: (item.page_number, item.line_start, item.candidate_id),
        )
        first = candidates[0]
        if any(
            candidate.attachment_url != first.attachment_url
            or candidate.raw_sha256 != first.raw_sha256
            or candidate.symbol != first.symbol
            for candidate in candidates[1:]
        ):
            raise ReviewPackageError(f"source candidate provenance diverges: {source_id}")
        raw = _fetch_pdf(client, first.attachment_url, attempts=fetch_attempts)
        raw_sha256 = hashlib.sha256(raw).hexdigest()
        if raw_sha256 != first.raw_sha256:
            raise ReviewPackageError(
                f"source bytes changed for {source_id}: "
                f"expected={first.raw_sha256}, observed={raw_sha256}"
            )
        pages, _ = extract_pdf_pages(raw)
        page_map = {page.page_number: page.lines for page in pages}
        if len(page_map) != len(pages):
            raise ReviewPackageError(f"duplicate extracted page number: {source_id}")
        try:
            company_name = company_names[first.symbol]
        except KeyError as exc:
            raise ReviewPackageError(f"candidate symbol absent from universe: {first.symbol}") from exc
        redaction_terms = _company_redaction_terms(company_name, first.symbol)
        for candidate in candidates:
            page_lines = page_map.get(candidate.page_number)
            if page_lines is None:
                raise ReviewPackageError(
                    f"candidate page absent after reconstruction: {candidate.candidate_id}"
                )
            payload = build_blind_review_payload(
                candidate,
                page_lines=page_lines,
                redaction_terms=redaction_terms,
                context_radius_lines=3,
            )
            payloads.append(payload)
            rejection = mechanical_rejection(payload)
            if rejection is not None:
                mechanical_decisions.append(
                    build_review_decision(
                        candidate_id=candidate.candidate_id,
                        blind_payload_sha256=payload.payload_sha256,
                        disposition="REJECTED",
                        reason_code=rejection,
                        reviewer_version="H003-V001-mechanical-v1",
                        reviewed_at_utc=datetime.now(UTC).isoformat(),
                        note=(
                            "Frozen deterministic mechanical rejection. "
                            "No semantic acceptance logic was applied."
                        ),
                    )
                )
        fetched_source_count += 1
        print(
            f"[{source_index}/{len(candidates_by_source)}] source={source_id[:12]} "
            f"candidates={len(candidates)}",
            flush=True,
        )

    payloads.sort(key=_payload_sort_key)
    mechanical_by_id = {decision.candidate_id: decision for decision in mechanical_decisions}
    semantic_payloads = [
        payload for payload in payloads if payload.candidate_id not in mechanical_by_id
    ]
    package_unsigned = {
        "schema_version": 1,
        "review_rule_id": REVIEW_RULE_ID,
        "review_rule_sha256": REVIEW_RULE_SHA256,
        "candidate_report_sha256": corpus.report_sha256,
        "candidate_count": corpus.candidate_count,
        "fetched_source_count": fetched_source_count,
        "blind_payload_count": len(payloads),
        "mechanical_rejected_count": len(mechanical_decisions),
        "semantic_review_count": len(semantic_payloads),
        "blind_payload_sha256": _canonical_hash([payload.to_dict() for payload in payloads]),
        "mechanical_decisions_sha256": _canonical_hash(
            [decision.to_dict() for decision in sorted(mechanical_decisions, key=lambda x: x.candidate_id)]
        ),
        "semantic_queue_sha256": _canonical_hash(
            [payload.to_dict() for payload in semantic_payloads]
        ),
    }
    return (
        {**package_unsigned, "package_sha256": _canonical_hash(package_unsigned)},
        payloads,
        mechanical_decisions,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the blind H003-V001 review package from a complete E002 corpus."
    )
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--review-rule", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--fetch-attempts", type=int, default=4)
    args = parser.parse_args()
    if args.fetch_attempts < 1:
        parser.error("--fetch-attempts must be at least 1")

    load_and_validate_review_rule(args.review_rule)
    corpus = load_complete_candidate_corpus(args.candidate_report)
    company_names = _load_company_names(args.universe)
    package, payloads, mechanical_decisions = build_package(
        corpus,
        company_names=company_names,
        client=NSEClient(timeout=30.0, attempts=3),
        fetch_attempts=args.fetch_attempts,
    )
    mechanical_ids = {decision.candidate_id for decision in mechanical_decisions}
    semantic_payloads = [
        payload for payload in payloads if payload.candidate_id not in mechanical_ids
    ]
    out = args.out_dir
    _write_json(out / "package.json", package)
    _write_json(out / "blind-payloads.json", [payload.to_dict() for payload in payloads])
    _write_json(
        out / "mechanical-decisions.json",
        [decision.to_dict() for decision in sorted(mechanical_decisions, key=lambda x: x.candidate_id)],
    )
    _write_json(
        out / "semantic-review-queue.json",
        [payload.to_dict() for payload in semantic_payloads],
    )
    print(json.dumps(package, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
