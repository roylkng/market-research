"""Fetch original Zuari FY26 issuer annual PDF with real retrieval time.

Always retain a source attempt. Only a validated issuer/year original is saved
as proof. The annual dated loan schedules cannot be called current redemption.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p026_zuari_annual import (
    URL,
    validated_receipt,
    verify_receipt,
)

ORIGINALS = Path("research/l001/originals/zuari_fy26_annual")
MAX_BYTES = 70_000_000


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != raw:
            raise AlphaContractError(f"P026 original source collision: {path}")
        return
    path.write_bytes(raw)


def _download(url: str) -> tuple[int | None, bytes | None, str | None]:
    if url != URL:
        raise AlphaContractError("P026 unapproved original issuer URL")
    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/pdf",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=65,
            stream=True,
            allow_redirects=False,
        )
        if r.status_code != 200:
            r.close()
            return r.status_code, None, None
        buf = bytearray()
        for chunk in r.iter_content(chunk_size=1024 * 128):
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                r.close()
                return 200, None, "OVER_SOURCE_SIZE_CAP"
        r.close()
        return 200, bytes(buf), None
    except requests.RequestException as exc:
        return None, None, type(exc).__name__


def run(root: Path, *, attempt_id: str) -> dict:
    if not attempt_id or any(x in attempt_id for x in ("/", "\\", "..")):
        raise AlphaContractError("P026 invalid original annual run identity")
    status, raw, error = _download(URL)
    captured = datetime.now(UTC).isoformat()
    attempt: dict = {
        "schema_version": 1,
        "issuer": "ZUARIIND",
        "source_url": URL,
        "captured_at_utc": captured,
        "http_status": status,
        "error_class": error,
        "state": "ORIGINAL_ISSUER_ANNUAL_SOURCE_NOT_AVAILABLE",
        "source_original_raw_sha256": None,
        "source_original_raw_path": None,
        "source_receipt_sha256": None,
        "live_capital_allowed": False,
    }
    if status == 200 and raw:
        try:
            attested = validated_receipt(raw, observed_utc=captured)
        except (AlphaContractError, ValueError) as exc:
            attempt["state"] = "BLOCKED_ORIGINAL_ANNUAL_IDENTITY_OR_CONTENT"
            attempt["error_class"] = type(exc).__name__
            attempt["error_detail"] = str(exc)[:330]
        else:
            _write_once(root / attested["original_raw_path"], raw)
            _write_once(
                root / ORIGINALS / "receipts" / (
                    f"{attested['original_raw_pdf_sha256']}.json"
                ),
                (json.dumps(attested, sort_keys=True, indent=2) + "\n").encode(),
            )
            attempt["state"] = "ORIGINAL_FY26_ANNUAL_PDF_ARCHIVED"
            attempt["source_original_raw_sha256"] = attested[
                "original_raw_pdf_sha256"
            ]
            attempt["source_original_raw_path"] = attested["original_raw_path"]
            attempt["source_receipt_sha256"] = attested["receipt_sha256"]
            attempt["error_class"] = None
    attempt["attempt_sha256"] = digest(attempt)
    _write_once(
        root / ORIGINALS / "attempts" / f"{attempt_id}.json",
        (json.dumps(attempt, sort_keys=True, indent=2) + "\n").encode(),
    )
    return attempt


def check(root: Path) -> dict:
    evidence = root / ORIGINALS / "receipts"
    receipts = sorted(evidence.glob("*.json")) if evidence.is_dir() else []
    sha_list = []
    num_matched = 0
    for file in receipts:
        receipt = json.loads(file.read_text("utf-8"))
        raw = (root / receipt["original_raw_path"]).read_bytes()
        verify_receipt(raw, receipt)
        sha_list.append(receipt["original_raw_pdf_sha256"])
        num_matched += receipt["source_evidence"]["matched_independent_note_count"]
    return {
        "state": (
            "FY26_ORIGINAL_ANNUAL_SOURCE_REPLAYED"
            if receipts else "FY26_ORIGINAL_ANNUAL_SOURCE_PENDING"
        ),
        "source_receipt_count": len(receipts),
        "loan_security_same_page_note_matches": num_matched,
        "original_source_hashes": sha_list,
        "october_2026_lien_clearance_verified": False,
        "investable_equity_NAV_verified": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = (
        check(args.repo_root) if args.check
        else run(args.repo_root, attempt_id=args.run_id)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
