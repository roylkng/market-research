from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected one patch target in {path}, found {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/marketlab/h003_review.py"
replace_once(
    path,
    '''    original_excerpt = " ".join(page_lines[candidate.line_start - 1 : candidate.line_end])
    if " ".join(original_excerpt.split()) != " ".join(candidate.excerpt.split()):
        raise H003ReviewError("reconstructed source lines do not match candidate excerpt")
''',
    '''    original_excerpt = " ".join(page_lines[candidate.line_start - 1 : candidate.line_end])
    expected_excerpt = " ".join(original_excerpt.split())
    if len(expected_excerpt) > 600:
        expected_excerpt = expected_excerpt[:600].rstrip()
    if expected_excerpt != " ".join(candidate.excerpt.split()):
        raise H003ReviewError("reconstructed source lines do not match candidate excerpt")
''',
)
replace_once(
    path,
    '''    context = "\\n".join(payload.redacted_page_context).casefold()
    if any(marker in lowered for marker in EXCLUDE_MARKERS):
        return "REJECT_OTHER_WITH_EXPLICIT_NOTE"
    if "?" in text:
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    stripped = re.sub(r"^[^a-zA-Z]+", "", lowered)
    if any(stripped.startswith(prefix) for prefix in QUESTION_PREFIXES):
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    if any(re.search(rf"\\b{re.escape(label)}\\s*[:\\-]", context) for label in NON_MANAGEMENT_LABELS):
        # A nearby speaker label is a high-confidence rejection only when it is on
        # the candidate excerpt itself or the immediately preceding context line.
        immediate = "\\n".join(payload.redacted_page_context[:4]).casefold()
        if any(
            re.search(rf"\\b{re.escape(label)}\\s*[:\\-]", immediate)
            for label in NON_MANAGEMENT_LABELS
        ):
            return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    return None
''',
    '''    if any(marker in lowered for marker in EXCLUDE_MARKERS):
        return "REJECT_OTHER_WITH_EXPLICIT_NOTE"
    if "?" in text:
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    stripped = re.sub(r"^[^a-zA-Z]+", "", lowered)
    if any(stripped.startswith(prefix) for prefix in QUESTION_PREFIXES):
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    if any(
        re.search(rf"\\b{re.escape(label)}\\s*[:\\-]", lowered)
        for label in NON_MANAGEMENT_LABELS
    ):
        return "REJECT_QUESTION_OR_NON_MANAGEMENT_SPEAKER"
    return None
''',
)
replace_once(
    path,
    '''def _claim_id(candidate_id: str, draft: NormalizedClaimDraft) -> str:
    return "H003C-" + _canonical_hash(
        {"candidate_id": candidate_id, "normalized_claim": draft.to_dict()}
    )[:20]


def _management_claim(candidate: ClaimCandidate, draft: NormalizedClaimDraft) -> ManagementClaim:
''',
    '''def _claim_id(
    candidate_id: str,
    decision_id: str,
    draft: NormalizedClaimDraft,
) -> str:
    return "H003C-" + _canonical_hash(
        {
            "candidate_id": candidate_id,
            "decision_id": decision_id,
            "normalized_claim": draft.to_dict(),
        }
    )[:20]


def _management_claim(
    candidate: ClaimCandidate,
    decision_id: str,
    draft: NormalizedClaimDraft,
) -> ManagementClaim:
''',
)
replace_once(
    path,
    '''        claim_id=_claim_id(candidate.candidate_id, draft),
''',
    '''        claim_id=_claim_id(candidate.candidate_id, decision_id, draft),
''',
)
replace_once(
    path,
    '''            f"candidate={candidate.candidate_id};page={candidate.page_number};"
            f"lines={candidate.line_start}-{candidate.line_end}"
''',
    '''            f"candidate={candidate.candidate_id};decision={decision_id};"
            f"page={candidate.page_number};lines={candidate.line_start}-{candidate.line_end}"
''',
)
replace_once(
    path,
    '''def freeze_review_ledger(
    corpus: CandidateCorpus,
    decisions: list[ReviewDecision],
) -> ReviewLedger:
    by_candidate: dict[str, ReviewDecision] = {}
''',
    '''def freeze_review_ledger(
    corpus: CandidateCorpus,
    decisions: list[ReviewDecision],
    blind_payloads: list[BlindReviewPayload],
) -> ReviewLedger:
    payload_by_candidate: dict[str, BlindReviewPayload] = {}
    for blind_payload in blind_payloads:
        payload_document = blind_payload.to_dict()
        declared_payload_hash = payload_document.pop("payload_sha256", None)
        if (
            blind_payload.schema_version != 1
            or blind_payload.review_rule_id != REVIEW_RULE_ID
            or blind_payload.review_rule_sha256 != REVIEW_RULE_SHA256
            or declared_payload_hash != _canonical_hash(payload_document)
        ):
            raise H003ReviewError(
                f"invalid blind review payload: {blind_payload.candidate_id}"
            )
        candidate = corpus.candidates_by_id.get(blind_payload.candidate_id)
        if candidate is None:
            raise H003ReviewError(
                f"blind payload references unknown candidate: {blind_payload.candidate_id}"
            )
        if blind_payload.evidence_sha256 != _candidate_evidence_hash(candidate):
            raise H003ReviewError(
                f"blind payload evidence hash mismatch: {blind_payload.candidate_id}"
            )
        if blind_payload.candidate_id in payload_by_candidate:
            raise H003ReviewError(
                f"duplicate blind review payload: {blind_payload.candidate_id}"
            )
        payload_by_candidate[blind_payload.candidate_id] = blind_payload
    payload_missing = sorted(set(corpus.candidates_by_id) - set(payload_by_candidate))
    if payload_missing:
        raise H003ReviewError(
            f"blind payload coverage incomplete; missing={len(payload_missing)}"
        )

    by_candidate: dict[str, ReviewDecision] = {}
''',
)
replace_once(
    path,
    '''        if decision.candidate_id in by_candidate:
            raise H003ReviewError(f"duplicate review decision: {decision.candidate_id}")
        by_candidate[decision.candidate_id] = decision
''',
    '''        if decision.candidate_id in by_candidate:
            raise H003ReviewError(f"duplicate review decision: {decision.candidate_id}")
        blind_payload = payload_by_candidate[decision.candidate_id]
        if decision.blind_payload_sha256 != blind_payload.payload_sha256:
            raise H003ReviewError(
                f"decision blind-payload hash mismatch: {decision.candidate_id}"
            )
        by_candidate[decision.candidate_id] = decision
''',
)
replace_once(
    path,
    '''            accepted_claims.append(_management_claim(candidate, decision.normalized_claim))
''',
    '''            accepted_claims.append(
                _management_claim(candidate, decision.decision_id, decision.normalized_claim)
            )
''',
)

# Test fixture corrections and stronger payload binding checks.
test_path = "tests/test_h003_review.py"
replace_once(
    test_path,
    '''    candidate = _candidate(excerpt="Why is our guidance only 1% to 3% for next year?")
    payload = _payload(candidate, ("Why is our guidance only 1% to 3% for next year?",))
''',
    '''    candidate = _candidate(
        excerpt="Why is our guidance only 1% to 3% for next year?",
        line_start=1,
        line_end=1,
    )
    payload = _payload(candidate, ("Why is our guidance only 1% to 3% for next year?",))
''',
)
replace_once(
    test_path,
    '''    ledger = freeze_review_ledger(corpus, [accepted, rejected])
''',
    '''    ledger = freeze_review_ledger(
        corpus,
        [accepted, rejected],
        [accepted_payload, rejected_payload],
    )
''',
)
replace_once(
    test_path,
    '''        freeze_review_ledger(corpus, [])
''',
    '''        freeze_review_ledger(corpus, [], [])
''',
)

Path(test_path).write_text(
    Path(test_path).read_text(encoding="utf-8")
    + '''\n\ndef test_wrong_blind_payload_hash_blocks_freeze():
    candidate = _candidate(candidate_id="cand-bind")
    corpus = CandidateCorpus(
        report_sha256="c" * 64,
        candidate_rule_id="H003-E002",
        candidate_rule_sha256=candidate.rule_sha256,
        source_bundle_sha256="583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee",
        cohort_id="FY27-Q2-2026-09-06",
        candidate_count=1,
        candidates_by_id={candidate.candidate_id: candidate},
    )
    payload = _payload(
        candidate,
        ("Analyst question", "We expect revenue growth of 15% next year."),
    )
    decision = build_review_decision(
        candidate_id=candidate.candidate_id,
        blind_payload_sha256="0" * 64,
        disposition="REJECTED",
        reason_code="REJECT_GENERIC_ASPIRATION",
        reviewer_version="blind-review-v1",
        reviewed_at_utc="2026-09-07T00:00:00Z",
    )
    with pytest.raises(H003ReviewError, match="blind-payload hash mismatch"):
        freeze_review_ledger(corpus, [decision], [payload])
''',
    encoding="utf-8",
)
