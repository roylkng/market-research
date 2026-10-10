"""Render six hash-pinned original BSE WWIL PDF pages to verifiable PNG.

The images enable visual inspection of the original Annexure A/B layout,
but the renderer itself does *not* approve semantic facts or share economics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from marketlab.hg007_original_pages import EXPECTED_SHA, ORIGINAL_PATH
from marketlab.hg007_wwil_terms_review import load_verified_page_text

RENDER_ID = "HG007-P006-INOXGREEN-ORIGINAL-SIX-PAGE-VISUAL-SOURCE-v1"
EXPECTED_PAGES = 6
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_info(raw: bytes) -> tuple[int, int]:
    if not isinstance(raw, bytes) or len(raw) < 45:
        raise ValueError("original-page PNG bytes missing/too short")
    if raw[:8] != PNG_SIGNATURE or raw[12:16] != b"IHDR":
        raise ValueError("unexpected image signature or PNG IHDR")
    width, height = struct.unpack(">II", raw[16:24])
    if not 300 <= width <= 3000 or not 300 <= height <= 4000:
        raise ValueError("render image dimension outside visual-review contract")
    if b"IEND" not in raw[-16:]:
        raise ValueError("rendered original PNG trailer missing")
    return width, height


def render_original_wwil_page_images(
    repo_root: Path, output_dir: Path, *, max_page_dimension: int = 1600
) -> dict[str, Any]:
    if type(max_page_dimension) is not int or not 800 <= max_page_dimension <= 2400:
        raise ValueError("page render dimension must be in [800,2400] px")
    original = repo_root / ORIGINAL_PATH
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA:
        raise ValueError("original PDF SHA no longer matches pinned BSE original")
    source_pages = load_verified_page_text(repo_root)
    if source_pages["page_count"] != EXPECTED_PAGES:
        raise ValueError("original PDF page count changed")
    binary = shutil.which("pdftoppm")
    if binary is None:
        raise FileNotFoundError("pdftoppm/Poppler required for source visuals")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wwil-bse-render-") as directory:
        prefix = Path(directory) / "original-page"
        subprocess.run(
            [
                binary, "-f", "1", "-l", str(EXPECTED_PAGES),
                "-scale-to", str(max_page_dimension),
                "-gray", "-png", str(original), str(prefix),
            ],
            check=True,
            timeout=110,
            capture_output=True,
        )
        rendered: dict[int, bytes] = {}
        for path in Path(directory).glob("original-page-*.png"):
            raw_png = path.read_bytes()
            page_idx = int(path.stem.rsplit("-", 1)[1])
            if page_idx in rendered or page_idx not in range(1, EXPECTED_PAGES + 1):
                raise ValueError("duplicate/unexpected render page number")
            _png_info(raw_png)
            rendered[page_idx] = raw_png
        if set(rendered) != set(range(1, EXPECTED_PAGES + 1)):
            raise ValueError("not all six original page PNGs rendered")

        pages: list[dict[str, Any]] = []
        for page_idx, raw_png in sorted(rendered.items()):
            width, height = _png_info(raw_png)
            target = output_dir / f"original-page-{page_idx:02d}.png"
            if target.exists() and target.read_bytes() != raw_png:
                raise ValueError("immutable original page render differs from current output")
            target.write_bytes(raw_png)
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != hashlib.sha256(raw_png).hexdigest():
                raise ValueError("rendered original page bytes changed on disk")
            pages.append({
                "page": page_idx,
                "original_pdf_sha256": EXPECTED_SHA,
                "source_page_text_sha256": source_pages["pages"][page_idx - 1]["text_sha256"],
                "render_png_sha256": actual,
                "render_png_size": len(raw_png),
                "png_width": width,
                "png_height": height,
                "filename": target.name,
                "visual_semantic_review_completed": False,
            })

    packet = {
        "schema_version": 1,
        "render_id": RENDER_ID,
        "classification": "ORIGINAL_BSE_PDF_PAGE_VISUALS_NOT_SEMANTIC_APPROVAL",
        "original_pdf_sha256": EXPECTED_SHA,
        "original_pdf_pages": EXPECTED_PAGES,
        "renderer": "pdftoppm_poppler_grayscale_png",
        "max_dimension_px": max_page_dimension,
        "pages": pages,
        "original_source_text_extracted_and_sha_verified": True,
        "original_page_visuals_available_for_review": True,
        "page_by_page_visual_semantic_audit_completed": False,
        "legal_wwil_transfer_completed_verified": False,
        "loan_conversion_classes_and_prices_verified": False,
        "wwil_normalized_earnings_verified": False,
        "current_company_completion_probabilities_published": False,
        "equity_expected_returns_calculated": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    receipt = output_dir / "source-render-manifest-v1.json"
    encoded = json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if receipt.exists() and receipt.read_text(encoding="utf-8") != encoded:
        raise ValueError("original PNG source render manifest changed")
    receipt.write_text(encoded, encoding="utf-8")
    return packet


def validate_original_render(output_dir: Path) -> dict[str, Any]:
    manifest = output_dir / "source-render-manifest-v1.json"
    packet = json.loads(manifest.read_text(encoding="utf-8"))
    if (
        packet.get("render_id") != RENDER_ID
        or packet.get("original_pdf_sha256") != EXPECTED_SHA
        or packet.get("original_pdf_pages") != EXPECTED_PAGES
    ):
        raise ValueError("unrecognized original BSE source render")
    rows = packet.get("pages")
    if not isinstance(rows, list) or len(rows) != EXPECTED_PAGES:
        raise ValueError("source render page count changed")
    for idx, page in enumerate(rows, 1):
        if page.get("page") != idx or page.get("filename") != f"original-page-{idx:02d}.png":
            raise ValueError("source render pages reordered")
        raw = (output_dir / page["filename"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != page.get("render_png_sha256"):
            raise ValueError("original page render PNG sha mismatch")
        if (page["png_width"], page["png_height"]) != _png_info(raw):
            raise ValueError("original page render dimension changed")
        if page.get("visual_semantic_review_completed") is not False:
            raise ValueError("visual review may not be implicitly approved")
    for flag in (
        "page_by_page_visual_semantic_audit_completed",
        "legal_wwil_transfer_completed_verified",
        "loan_conversion_classes_and_prices_verified",
        "wwil_normalized_earnings_verified",
        "current_company_completion_probabilities_published",
        "equity_expected_returns_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"rendered pages cannot establish {flag}")
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--max-dimension", type=int, default=1600)
    args = parser.parse_args()
    packet = render_original_wwil_page_images(
        args.repo_root, args.out_dir, max_page_dimension=args.max_dimension
    )
    validate_original_render(args.out_dir)
    print(json.dumps({
        "render_id": packet["render_id"],
        "page_count": len(packet["pages"]),
        "original_pdf_sha256": packet["original_pdf_sha256"],
        "render_png_sha256": [page["render_png_sha256"] for page in packet["pages"]],
        "visual_review_completed": packet["page_by_page_visual_semantic_audit_completed"],
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
