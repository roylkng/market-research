from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

import pytest

from scripts.render_hg007_npst_original_tables import (
    DOCUMENTS,
    RENDER_ID,
    _png_dimensions,
    render_original_financial_pages,
    validate_source_visuals,
)


def test_rejects_fake_png_image_header_and_resolution() -> None:
    with pytest.raises(ValueError, match="complete PNG"):
        _png_dimensions(b"not a PNG")
    bad = b"\x89PNG\r\n\x1a\n" + b"x" * 4 + b"IHDR" + struct.pack(">II", 200, 200)
    bad += b"x" * 50 + b"IEND"
    with pytest.raises(ValueError, match="resolution"):
        _png_dimensions(bad)


def test_source_render_requires_bounded_image_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="maximum source image dimension"):
        render_original_financial_pages(
            Path("."), tmp_path, max_side=700
        )


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler missing")
def test_original_issuer_pages_and_sha_are_visually_ready_not_approved(
    tmp_path: Path,
) -> None:
    source = render_original_financial_pages(
        Path("."), tmp_path, max_side=1250
    )
    assert source["render_id"] == RENDER_ID
    assert source["selected_page_count"] == 5
    assert validate_source_visuals(tmp_path) == source
    expected = {
        ("presentation", 18),
        ("presentation", 19),
        ("presentation", 20),
        ("reg32", 2),
        ("reg32", 3),
    }
    actual = {
        (r["document_source_role"], r["original_page_number"])
        for r in source["rendered_pages"]
    }
    assert actual == expected
    for row in source["rendered_pages"]:
        assert row["original_pdf_sha256"] == DOCUMENTS[
            row["document_source_role"]
        ]["sha256"]
        assert len(row["original_page_text_sha256"]) == 64
        assert len(row["image_sha256"]) == 64
        assert (tmp_path / row["file_name"]).is_file()
        assert row["layout_and_visual_semantics_independently_reviewed"] is False
    assert source["page_layout_review_approved"] is False
    assert source["unspent_reg32_funds_as_bank_cash_proven"] is False
    assert source["presentation_graphic_versus_table_numeric_discrepancy_resolved"] is False
    assert source["return_forecast_or_equity_price_target_calculated"] is False
    assert source["live_capital_allowed"] is False


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler missing")
def test_original_source_immutable_and_never_semantically_promoted(
    tmp_path: Path,
) -> None:
    render_original_financial_pages(Path("."), tmp_path, max_side=1050)
    page = tmp_path / "reg32-original-page-02.png"
    raw = page.read_bytes()
    page.write_bytes(raw + b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_source_visuals(tmp_path)
    page.write_bytes(raw)
    packet = json.loads(
        (tmp_path / "source-visuals-v1.json").read_text(encoding="utf-8")
    )
    packet["page_layout_review_approved"] = True
    (tmp_path / "source-visuals-v1.json").write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="cannot promote"):
        validate_source_visuals(tmp_path)


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler missing")
def test_rerender_does_not_change_six_original_bse_pdf_sources(
    tmp_path: Path,
) -> None:
    original = render_original_financial_pages(
        Path("."), tmp_path, max_side=1000
    )
    again = render_original_financial_pages(
        Path("."), tmp_path, max_side=1000
    )
    assert again == original
