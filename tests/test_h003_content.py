from marketlab.h003_content import (
    CONTENT_RULE_SHA256,
    SOURCE_BUNDLE_SHA256,
    classify_extracted_text,
    load_and_validate_content_rule,
    load_frozen_sources,
)


def test_frozen_h003_content_rule_validates():
    document = load_and_validate_content_rule("registry/h003_content_rule.yaml")
    assert document["sha256"] == CONTENT_RULE_SHA256
    assert document["source_bundle_sha256"] == SOURCE_BUNDLE_SHA256
    assert document["live_capital"] is False


def test_frozen_source_bundle_resolves_exactly_794_sources():
    sources = load_frozen_sources(
        "research/prospective/h003/FY27-Q2-2026-09-06/source-coverage-v1.json"
    )
    assert len(sources) == 794
    assert len({source.source_id for source in sources}) == 794
    assert len({source.attachment_url for source in sources}) == 794


def test_content_ready_requires_multiple_pages_and_substantive_text():
    pages = ("A" * 3000, "B" * 3000)
    assert classify_extracted_text(pages, "\n".join(pages)) == "CONTENT_READY"


def test_one_page_exchange_notice_is_insufficient_even_if_long():
    pages = ("A" * 10000,)
    assert classify_extracted_text(pages, pages[0]) == "INSUFFICIENT_TEXT"


def test_multi_page_but_sparse_extraction_is_insufficient():
    pages = ("notice", "link")
    assert classify_extracted_text(pages, "\n".join(pages)) == "INSUFFICIENT_TEXT"


def test_empty_scan_is_insufficient_not_content_ready():
    assert classify_extracted_text(("", ""), "") == "INSUFFICIENT_TEXT"
