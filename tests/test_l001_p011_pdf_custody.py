"""L001 P011: no wrong-host, fabricated, or backdated issuer PDF evidence."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.materialize_l001_p011_issuer_pdf_custody import (
    SOURCE_SPEC,
    _claims,
    _pdf_text,
    _policy,
    materialize_sources,
)


def test_allowed_issuer_hosts_are_exact_not_suffix_guesses():
    assert _policy("https://greatship.com/upload/original.pdf")
    assert _policy("https://www.zuari.in/assets/files/original.pdf")
    assert not _policy("http://www.zuari.in/original.pdf")
    assert not _policy("https://www.zuari.in.bad.example/doc.pdf")
    assert not _policy("https://example.com/zuari.pdf")


def test_claims_are_bound_to_pdf_text_not_value_guessing():
    text = "Net strategic holdings INR 4,223 crores, Chambal Fertilisers 59.5m"
    assert _claims(text, ("4,223", "Chambal")) == []
    assert _claims(text, ("5,223", "Chambal")) == ["5,223"]


def test_invalid_or_zero_pdf_is_not_original():
    for raw in (b"", b"<html>not PDF</html>", b"%PDF-4", b"\x00" * 600):
        with pytest.raises(ValueError):
            _pdf_text(raw)


def test_original_source_schema_admission_with_mock_transport():
    class FakeResponse:
        def __init__(self, url):
            self.url = url
            self.content = b"%PDF-" + b"f" * 600
        def raise_for_status(self):
            return None

    with patch(
        "scripts.materialize_l001_p011_issuer_pdf_custody._pdf_text",
        side_effect=lambda raw: (1, " ".join(
            token for _, _, _, tokens in SOURCE_SPEC for token in tokens
        )),
    ):
        manifest, sources = materialize_sources(
            fetcher=lambda url, **kwargs: FakeResponse(url),
        )
    assert manifest["source_count"] == 6
    assert len(sources) == 6
    assert manifest["no_retrospective_lookahead_claims"] is True
    assert all(
        row["historical_decision_date_original_byte_custody_proven"] is False
        and row["actual_first_verified_capture_utc"].endswith("Z")
        for row in manifest["sources"]
    )


def test_spoofed_final_transport_host_fails():
    class FakeResponse:
        url = "https://www.zuari.in.malicious.test/file.pdf"
        content = b"%PDF-" + b"f" * 600
        def raise_for_status(self):
            return None

    with pytest.raises(ValueError, match="unapproved host"):
        materialize_sources(fetcher=lambda url, **kwargs: FakeResponse())


def test_source_token_mismatch_blocks_capture():
    class FakeResponse:
        def __init__(self, url):
            self.url = url
            self.content = b"%PDF-" + b"f" * 600
        def raise_for_status(self):
            return None

    with (
        patch(
            "scripts.materialize_l001_p011_issuer_pdf_custody._pdf_text",
            return_value=(1, "company name only, no numeric evidence"),
        ),
        pytest.raises(ValueError, match="required original numeric"),
    ):
        materialize_sources(fetcher=lambda url, **kwargs: FakeResponse(url))
