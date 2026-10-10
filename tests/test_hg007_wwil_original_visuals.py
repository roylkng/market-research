from __future__ import annotations

import hashlib
import json
import shutil
import struct
from pathlib import Path

import pytest

from scripts.render_hg007_wwil_original_pages import (
    EXPECTED_PAGES,
    EXPECTED_SHA,
    _png_info,
    render_original_wwil_page_images,
    validate_original_render,
)


def test_png_header_validation_rejects_malformed_source() -> None:
    with pytest.raises(ValueError, match="missing/too short"):
        _png_info(b"anything")
    forged = b"\x89PNG\r\n\x1a\n" + b"abcd" + b"IHDR" + (
        struct.pack(">II", 1600, 1800)
    ) + b"f" * 100
    with pytest.raises(ValueError, match="trailer"):
        _png_info(forged)


def test_renderer_never_accepts_trust_flags_or_invalid_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dimension"):
        render_original_wwil_page_images(Path("."), tmp_path, max_page_dimension=700)


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler unavailable")
def test_render_original_six_page_source_and_retention(tmp_path: Path) -> None:
    out = tmp_path / "pages"
    result = render_original_wwil_page_images(Path("."), out, max_page_dimension=1100)
    assert result["original_pdf_sha256"] == EXPECTED_SHA
    assert result["original_pdf_pages"] == EXPECTED_PAGES
    assert len(result["pages"]) == EXPECTED_PAGES
    assert result["page_by_page_visual_semantic_audit_completed"] is False
    assert result["live_capital_allowed"] is False
    for idx, page in enumerate(result["pages"], 1):
        png = out / f"original-page-{idx:02d}.png"
        raw = png.read_bytes()
        assert page["png_width"] > 300
        assert page["png_height"] > 300
        assert page["render_png_sha256"] == hashlib.sha256(raw).hexdigest()
        assert page["visual_semantic_review_completed"] is False
    assert validate_original_render(out) == result


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler unavailable")
def test_tampering_with_png_source_and_semantic_review_is_rejected(tmp_path: Path) -> None:
    out = tmp_path / "pages"
    render_original_wwil_page_images(Path("."), out, max_page_dimension=1100)
    receipt = out / "source-render-manifest-v1.json"
    result = json.loads(receipt.read_text(encoding="utf-8"))
    result["page_by_page_visual_semantic_audit_completed"] = True
    receipt.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot establish"):
        validate_original_render(out)

    render_source = out / "original-page-05.png"
    raw = render_source.read_bytes()
    render_source.write_bytes(raw + b"x")
    with pytest.raises(ValueError, match="sha mismatch"):
        validate_original_render(out)
