"""Archive Zuari's original presentation PDF, or seal an explicit blocked receipt.

Source bytes are obtained NOW, not backdated to the August announcement.
No source-only archive updates a previously signed valuation packet.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p025_zuari_pdf import (
    RECEIPT_ID,
    URL,
    validated_original_receipt,
    verify_original_receipt,
)

ORIGINAL_DIR = Path("research/l001/originals/zuari_q1")
MAX_RESPONSE = 20_000_000


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise AlphaContractError(f"P025 append-only source collision: {path}")
        return
    path.write_bytes(raw)


def _fetch() -> tuple[int | None, bytes | None, str | None]:
    try:
        response = requests.get(
            URL,
            headers={
                "Accept": "application/pdf",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=40,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code != 200:
            response.close()
            return response.status_code, None, None
        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > MAX_RESPONSE:
                response.close()
                return 200, None, "PDF_TOO_LARGE"
        response.close()
        return 200, bytes(content), None
    except requests.RequestException as exc:
        return None, None, type(exc).__name__


def _run(root: Path, *, run_id: str) -> dict:
    if not run_id or any(char in run_id for char in ("/", "\\", "..")):
        raise AlphaContractError("P025 unsafe original source attempt identity")
    status, raw, error = _fetch()
    observed = datetime.now(UTC).isoformat()
    receipt: dict = {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "source_url": URL,
        "actually_observed_at_utc": observed,
        "http_status": status,
        "error_class": error,
        "raw_sha256": None,
        "original_raw_repo_path": None,
        "source_state": "BLOCKED_ORIGINAL_ISSUER_PDF_HTTP_OR_NETWORK",
        "live_capital_allowed": False,
    }
    archived = False
    if status == 200 and raw:
        try:
            sealed = validated_original_receipt(raw, retrieved_at_utc=observed)
        except (AlphaContractError, ValueError) as exc:
            receipt["source_state"] = "BLOCKED_WRONG_OR_CHANGED_ISSUER_PDF"
            receipt["error_class"] = type(exc).__name__
            receipt["error_detail"] = str(exc)[:350]
        else:
            original = root / sealed["original_file_path"]
            _write_once(original, raw)
            _write_once(
                root / ORIGINAL_DIR / "receipts" / f"{sealed['raw_pdf_sha256']}.json",
                (json.dumps(sealed, sort_keys=True, indent=2) + "\n").encode(),
            )
            archived = True
            receipt["source_state"] = "ORIGINAL_ISSUER_PDF_BYTES_ARCHIVED"
            receipt["raw_sha256"] = sealed["raw_pdf_sha256"]
            receipt["original_raw_repo_path"] = sealed["original_file_path"]
            receipt["validated_receipt_sha256"] = sealed["receipt_sha256"]
            receipt["error_class"] = None
    receipt["attempt_sha256"] = digest(receipt)
    _write_once(
        root / ORIGINAL_DIR / "attempts" / f"{run_id}.json",
        (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode(),
    )
    return {
        "status": receipt["source_state"],
        "original_pdf_archive_created": archived,
        "original_pdf_raw_sha256": receipt["raw_sha256"],
        "actual_retrieved_at_utc": observed,
        "source_attempt_sha256": receipt["attempt_sha256"],
        "live_capital_allowed": False,
    }


def _check(root: Path) -> dict:
    receipt_dir = root / ORIGINAL_DIR / "receipts"
    receipts = sorted(receipt_dir.glob("*.json")) if receipt_dir.is_dir() else []
    verified = []
    for item in receipts:
        receipt = json.loads(item.read_text(encoding="utf-8"))
        raw = (root / receipt["original_file_path"]).read_bytes()
        verify_original_receipt(receipt, raw)
        verified.append(receipt["raw_pdf_sha256"])
    return {
        "status": (
            "ORIGINAL_ZUARI_ISSUER_PDF_REPLAYED"
            if verified else "ORIGINAL_ISSUER_PDF_SOURCE_PENDING"
        ),
        "validated_original_pdf_count": len(verified),
        "sha256": verified,
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", default="local")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    result = (
        _check(args.repo_root)
        if args.check else _run(args.repo_root, run_id=args.run_id)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
