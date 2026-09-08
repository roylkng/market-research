from __future__ import annotations

from marketlab.h003_outcomes import (
    ScoredPassage,
    SourcePassage,
    build_blind_outcome_payload,
)


def test_all_reviewer_visible_text_fields_are_identity_redacted() -> None:
    claim = {
        "claim_id": "H003C-12345678901234567890",
        "source_date": "2025-01-01",
        "normalized_claim": "ExampleBrand will launch ExampleBrand vehicles.",
        "claim_type": "ExampleBrand guidance",
        "metric": "ExampleBrand vehicles",
        "unit": "ExampleBrand units",
        "target_min": 10.0,
        "target_max": None,
        "target_deadline": None,
        "target_horizon": "ExampleBrand FY26",
    }
    passage = SourcePassage(
        source_alias="EVIDENCE_SOURCE_001",
        source_text_sha256="a" * 64,
        exchange_published_at_utc="2026-04-01T10:00:00Z",
        page_number=1,
        line_start=1,
        line_end=1,
        text="ExampleBrand delivered the target.",
        passage_id="H003P-" + "b" * 24,
    )
    selected = [ScoredPassage(passage=passage, score=5.0, matched_tokens=("target",))]
    packet = build_blind_outcome_payload(
        claim,
        selected,
        redaction_terms=["ExampleBrand"],
    )
    rendered = str(packet.to_dict())
    assert "ExampleBrand" not in rendered
    assert packet.normalized_claim.startswith("[COMPANY]")
    assert packet.claim_type.startswith("[COMPANY]")
    assert packet.metric.startswith("[COMPANY]")
    assert packet.unit is not None and packet.unit.startswith("[COMPANY]")
    assert packet.target_horizon is not None and packet.target_horizon.startswith("[COMPANY]")
    assert packet.evidence[0].text.startswith("[COMPANY]")
