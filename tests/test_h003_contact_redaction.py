from __future__ import annotations

import pytest

from marketlab.h003_identity_redaction import (
    H003IdentityRedactionError,
    assert_identity_scrubbed,
)
from marketlab.h003_outcomes import redact_company_identity


@pytest.mark.parametrize(
    ("raw", "forbidden"),
    [
        ("Email: mail@examplecompany.com", "examplecompany.com"),
        ("Web: www.examplecompany.com", "examplecompany.com"),
        ("See https://www.examplecompany.com/investors/report.pdf", "examplecompany.com"),
        ("portal examplecompany.co.in investor relations", "examplecompany.co.in"),
    ],
)
def test_contact_identifiers_are_redacted(raw: str, forbidden: str) -> None:
    redacted = redact_company_identity(raw, [])
    assert forbidden not in redacted.casefold()
    assert "[CONTACT]" in redacted


def test_contact_identifier_assertion_fails_closed() -> None:
    with pytest.raises(H003IdentityRedactionError, match="contact identifier survived"):
        assert_identity_scrubbed(
            {"evidence": [{"text": "Email mail@examplecompany.com"}]},
            [],
        )


def test_contact_identifier_assertion_accepts_redacted_packet() -> None:
    assert_identity_scrubbed(
        {"evidence": [{"text": "Email [CONTACT] Web [CONTACT]"}]},
        [],
    )
