"""Render selected original NPST Q1FY27 and June Reg32 pages for review.

Five original PDF pages are SHA-bound to P019's issuer source, with no
automatic visual economic fact approval. Never modify the original PDFs.
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

from marketlab.hg007_npst_june_facts import DOCUMENTS, load_npst_originals

RENDER_ID = "HG007-P021-NPST-2026-JUNE-ORIGINAL-FINANCIAL-TABLE-VISUALS-v1"
SELECTED_PAGES = {
    "presentation": (18, 19, 20),
    "reg32": (2, 3),
}
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_BYTES = 12_000_000


def _png_dimensions(raw: bytes) -> tuple[int, int]:
    if (
        not isinstance(raw, bytes)
        or not 64 <= len(raw) <= MAX_IMAGE_BYTES
        or raw[:8] != PNG_HEADER
        or raw[12:16] != b"IHDR"
        or b"IEND" not in raw[-32:]
    ):
        raise ValueError("source render must be complete PNG with IHDR/IEND")
    width, height = struct.unpack(">II", raw[16:24])
    if not (400 <= width <= 2600 and 400 <= height <= 2600):
        raise ValueError("source visual resolution outside allowed range")
    return width, height


def render_original_financial_pages(
    repo_root: Path,
    target_dir: Path,
    *,
    max_side: int = 1900,
) -> dict[str, Any]:
    if type(max_side) is not int or not 1000 <= max_side <= 2400:
        raise ValueError("maximum source image dimension must be 1000-2400")
    originals, _hurdle, receipts = load_npst_originals(repo_root)
    binary = shutil.which("pdftoppm")
    if binary is None:
        raise FileNotFoundError("Poppler pdftoppm is required for original visuals")

    with tempfile.TemporaryDirectory(prefix="npst-bse-pages-") as temp:
        scratch = Path(temp)
        stage = []
        for role, indices in SELECTED_PAGES.items():
            doc = originals[role]
            source = DOCUMENTS[role]
            pdf_path = (
                repo_root
                / "research/hg007/npst-aug2026-originals"
                / source["id"]
                / "raw"
                / "sha256"
                / f"{source['sha256']}.pdf"
            )
            for page in indices:
                temporary_prefix = scratch / f"{role}-page-{page:02d}"
                subprocess.run(
                    [
                        binary,
                        "-f", str(page),
                        "-l", str(page),
                        "-singlefile",
                        "-scale-to", str(max_side),
                        "-gray",
                        "-png",
                        str(pdf_path),
                        str(temporary_prefix),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=105,
                )
                raw = temporary_prefix.with_suffix(".png").read_bytes()
                width, height = _png_dimensions(raw)
                page_entry = doc["pages"][page - 1]
                stage.append((
                    f"{role}-original-page-{page:02d}.png",
                    raw,
                    {
                        "document_source_role": role,
                        "source_id": source["id"],
                        "original_pdf_sha256": source["sha256"],
                        "original_page_number": page,
                        "original_page_text_sha256": page_entry["extracted_text_sha256"],
                        "image_sha256": hashlib.sha256(raw).hexdigest(),
                        "image_byte_count": len(raw),
                        "png_width": width,
                        "png_height": height,
                        "layout_and_visual_semantics_independently_reviewed": False,
                    },
                ))
        if len(stage) != 5:
            raise ValueError("expected exactly three Q1 and two Reg32 original pages")

        packet: dict[str, Any] = {
            "schema_version": 1,
            "render_id": RENDER_ID,
            "classification": "EXACT_BSE_ORIGINAL_PDF_PAGES_FOR_VISUAL_REVIEW_NOT_AUDITED_FINANCIALS",
            "source_p019_original_page_spine_git_blob": receipts["p019_exact_source_blob"],
            "source_documents": {
                role: receipt
                for role, receipt in receipts.items()
                if role in DOCUMENTS
            },
            "render_max_side_px": max_side,
            "selected_page_count": len(stage),
            "rendered_pages": [
                {"file_name": name, **info} for name, _raw, info in stage
            ],
            "page_layout_review_approved": False,
            "unspent_reg32_funds_as_bank_cash_proven": False,
            "presentation_graphic_versus_table_numeric_discrepancy_resolved": False,
            "independent_npst_annual_earnings_approved": False,
            "return_forecast_or_equity_price_target_calculated": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        target_dir.mkdir(parents=True, exist_ok=True)
        for name, raw, _info in stage:
            dst = target_dir / name
            if dst.exists() and dst.read_bytes() != raw:
                raise ValueError("original source PNG already exists with different contents")
            dst.write_bytes(raw)
            if hashlib.sha256(dst.read_bytes()).digest() != hashlib.sha256(raw).digest():
                raise ValueError("source PNG bytes changed during immutable retention")
        manifest = target_dir / "source-visuals-v1.json"
        encoded = json.dumps(
            packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
        ) + "\n"
        if manifest.exists() and manifest.read_text(encoding="utf-8") != encoded:
            raise ValueError("original image source manifest already exists with other facts")
        manifest.write_text(encoded, encoding="utf-8")
        return packet


def validate_source_visuals(root: Path) -> dict[str, Any]:
    packet = json.loads((root / "source-visuals-v1.json").read_text(encoding="utf-8"))
    if (
        packet.get("render_id") != RENDER_ID
        or packet.get("selected_page_count") != 5
        or len(packet.get("rendered_pages", [])) != 5
    ):
        raise ValueError("visual source manifest identity/count mismatch")
    declared = {
        (role, page) for role, indices in SELECTED_PAGES.items() for page in indices
    }
    pairs = set()
    for row in packet["rendered_pages"]:
        role = row.get("document_source_role")
        page = row.get("original_page_number")
        filename = row.get("file_name")
        expected_name = f"{role}-original-page-{page:02d}.png"
        if (
            (role, page) not in declared or (role, page) in pairs
            or filename != expected_name
            or row.get("original_pdf_sha256") != DOCUMENTS[role]["sha256"]
            or row.get("layout_and_visual_semantics_independently_reviewed") is not False
        ):
            raise ValueError("incorrect original NPST visual source page or review status")
        pairs.add((role, page))
        raw = (root / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["image_sha256"]:
            raise ValueError("original NPST source page PNG digest mismatch")
        if _png_dimensions(raw) != (row["png_width"], row["png_height"]):
            raise ValueError("original NPST source page dimensions mismatch")
    if pairs != declared:
        raise ValueError("missing original NPST source page")
    for flag in (
        "page_layout_review_approved",
        "unspent_reg32_funds_as_bank_cash_proven",
        "presentation_graphic_versus_table_numeric_discrepancy_resolved",
        "independent_npst_annual_earnings_approved",
        "return_forecast_or_equity_price_target_calculated",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if packet.get(flag) is not False:
            raise ValueError(f"NPST source visuals cannot promote {flag}")
    return packet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-side", type=int, default=1900)
    args = parser.parse_args()
    rendered = render_original_financial_pages(
        args.repo_root, args.output_dir, max_side=args.max_side
    )
    validate_source_visuals(args.output_dir)
    print(json.dumps({
        "render_id": rendered["render_id"],
        "selected_page_count": rendered["selected_page_count"],
        "images": [
            {"name": row["file_name"], "sha256": row["image_sha256"]}
            for row in rendered["rendered_pages"]
        ],
        "visual_semantic_review_complete": False,
        "return_forecast_or_equity_price_target_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
