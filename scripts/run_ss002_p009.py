from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest
from marketlab.nse import NSEClient
from marketlab.ss002_p009_visual_review import build_p009_legibility_packet


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("P009 P008 source must be JSON object")
    return payload


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _retain_original(root: Path, raw: bytes, expected_sha: str) -> Path:
    if _sha(raw) != expected_sha or not raw.startswith(b"%PDF-"):
        raise AlphaContractError("P009 official PDF raw SHA/type mismatch")
    if len(raw) > 25_000_000:
        raise AlphaContractError("P009 official PDF exceeds frozen bounded input")
    path = root / "original-pdf" / "sha256" / f"{expected_sha}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise AlphaContractError("P009 content-addressed original PDF collision")
    path.write_bytes(raw)
    return path


def _render_page(
    source_pdf: Path, *,
    symbol: str,
    page_number: int,
    out_dir: Path,
) -> dict:
    stem = out_dir / "visual" / symbol / f"page-{page_number:04d}"
    stem.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pdftoppm",
            "-f", str(page_number),
            "-l", str(page_number),
            "-singlefile",
            "-jpeg",
            "-jpegopt", "quality=85",
            "-r", "110",
            str(source_pdf),
            str(stem),
        ],
        check=True,
        timeout=90,
        capture_output=True,
    )
    image_path = stem.with_suffix(".jpg")
    if not image_path.is_file():
        raise AlphaContractError("P009 page renderer produced no image")
    raw = image_path.read_bytes()
    if not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
        raise AlphaContractError("P009 rendered page is not a complete JPEG")
    return {
        "page_number": page_number,
        "relative_image_path": str(image_path.relative_to(out_dir)),
        "image_sha256": _sha(raw),
        "image_bytes": len(raw),
        "render_method": "pdftoppm-110dpi-jpeg85",
        "independent_semantic_review_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p008-review", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()

    if shutil.which("pdftoppm") is None:
        raise RuntimeError("P009 requires Poppler pdftoppm for original page rendering")

    packet = build_p009_legibility_packet(_load(args.p008_review))
    args.out.mkdir(parents=True, exist_ok=True)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    case_manifests = []
    for case in packet["cases"]:
        symbol = case["symbol"]
        raw = client.archive_bytes(case["official_nse_url"])
        source_path = _retain_original(
            args.out,
            raw,
            case["original_pdf_raw_sha256"],
        )
        try:
            reader = PdfReader(io.BytesIO(raw), strict=False)
            if reader.is_encrypted:
                raise AlphaContractError(f"{symbol}: encrypted original PDF is unsupported")
            observed_pages = len(reader.pages)
        except Exception as exc:
            raise AlphaContractError(f"{symbol}: original PDF page read failed") from exc
        if observed_pages != case["original_pdf_page_count"]:
            raise AlphaContractError(f"{symbol}: original PDF page count mismatch")

        page_images = []
        for page in case["pages"]:
            rendered = _render_page(
                source_path,
                symbol=symbol,
                page_number=page["page_number"],
                out_dir=args.out,
            )
            rendered["legibility_status"] = page["legibility_status"]
            rendered["source_segment_id"] = page["source_segment_id"]
            page_images.append(rendered)
        case_manifests.append(
            {
                "symbol": symbol,
                "document_id": case["document_id"],
                "official_nse_url": case["official_nse_url"],
                "original_pdf_sha256": _sha(raw),
                "original_pdf_byte_count": len(raw),
                "original_pdf_relative_path": str(source_path.relative_to(args.out)),
                "original_page_count": observed_pages,
                "rendered_page_count": len(page_images),
                "high_priority_visual_pages": case["priority_visual_pages"],
                "page_images": page_images,
                "independent_semantic_review_complete": False,
            }
        )
        print(
            f"[P009] {symbol}: rendered={len(page_images)} "
            f"priority_visual={case['priority_visual_pages']}",
            flush=True,
        )

    if sum(c["rendered_page_count"] for c in case_manifests) != 17:
        raise AlphaContractError("P009 failed to render all 17 original pages")

    visual_manifest = {
        "schema_version": 1,
        "render_id": "SS002-P009-VISUAL-v1",
        "classification": "SOURCE_RENDER_AND_REVIEW_INPUT_NOT_APPROVAL",
        "source_p009_pack_sha256": packet["pack_sha256"],
        "source_p008_pack_sha256": packet["source_p008_pack_sha256"],
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "case_count": len(case_manifests),
        "rendered_page_count": 17,
        "case_manifests": case_manifests,
        "independent_semantic_review_complete": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    visual_manifest["visual_manifest_sha256"] = digest(visual_manifest)
    (args.out / "ss002-p009-legibility.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n", encoding="utf-8"
    )
    (args.out / "ss002-p009-visual-manifest.json").write_text(
        json.dumps(visual_manifest, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pack_sha256": packet["pack_sha256"],
                "visual_manifest_sha256": visual_manifest["visual_manifest_sha256"],
                "legibility_state_counts": packet["legibility_state_counts"],
                "original_page_count": packet["original_page_count"],
                "rendered_page_count": visual_manifest["rendered_page_count"],
                "case_symbols": [c["symbol"] for c in case_manifests],
                "independent_semantic_review_complete": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
