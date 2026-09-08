from __future__ import annotations

from types import SimpleNamespace

import pytest

from marketlab.h003_identity_redaction import (
    H003IdentityRedactionError,
    assert_identity_scrubbed,
    combined_redaction_terms,
    company_redaction_terms,
    speaker_redaction_terms,
)
from marketlab.h003_outcomes import redact_company_identity


def selected(*texts: str):
    return [SimpleNamespace(passage=SimpleNamespace(text=text)) for text in texts]


def test_ultratech_short_name_is_redacted() -> None:
    terms = company_redaction_terms(
        {"company_name": "UltraTech Cement Ltd."},
        "ULTRACEMCO",
    )
    assert "UltraTech" in terms
    rendered = redact_company_identity(
        "UltraTech crossed a production-capacity milestone.",
        terms,
    )
    assert "UltraTech" not in rendered
    assert "[COMPANY]" in rendered


def test_apl_apollo_shortened_name_is_redacted_without_generic_tube_word() -> None:
    terms = company_redaction_terms(
        {"company_name": "APL Apollo Tubes Ltd."},
        "APLAPOLLO",
    )
    assert "APL Apollo" in terms
    assert "Apollo" in terms
    assert "Tubes" not in terms
    rendered = redact_company_identity("APL Apollo-branded products", terms)
    assert "APL Apollo" not in rendered


def test_group_prefix_is_redacted_but_generic_consumer_word_is_not() -> None:
    terms = company_redaction_terms(
        {"company_name": "Tata Consumer Products Ltd."},
        "TATACONSUM",
    )
    assert "Tata" in terms
    assert "Consumer" not in terms
    assert "Products" not in terms


def test_speaker_names_are_collected_from_selected_passages() -> None:
    terms = speaker_redaction_terms(
        selected(
            "Vinita Gupta: We are evaluating the launch channels.",
            "Dilip Banthiya: Margin improved during the year.",
        )
    )
    assert "Vinita Gupta" in terms
    assert "Dilip Banthiya" in terms


def test_combined_terms_scrub_company_and_speaker_names() -> None:
    passages = selected("Abhishek Khaitan: UltraTech will commission capacity.")
    terms = combined_redaction_terms(
        {"company_name": "UltraTech Cement Ltd."},
        "ULTRACEMCO",
        passages,
    )
    redacted = redact_company_identity(passages[0].passage.text, terms)
    assert "Abhishek Khaitan" not in redacted
    assert "UltraTech" not in redacted


def test_identity_assertion_fails_when_alias_survives() -> None:
    with pytest.raises(H003IdentityRedactionError, match="identity term survived"):
        assert_identity_scrubbed(
            {"evidence": [{"text": "UltraTech delivered the milestone."}]},
            ["UltraTech"],
        )


def test_identity_assertion_fails_on_unredacted_speaker_label() -> None:
    with pytest.raises(H003IdentityRedactionError, match="speaker labels survived"):
        assert_identity_scrubbed(
            {"evidence": [{"text": "Vinita Gupta: the target was achieved."}]},
            [],
        )


def test_identity_assertion_accepts_scrubbed_packet() -> None:
    assert_identity_scrubbed(
        {"evidence": [{"text": "[COMPANY]: the target was achieved."}]},
        ["UltraTech", "Vinita Gupta"],
    )
