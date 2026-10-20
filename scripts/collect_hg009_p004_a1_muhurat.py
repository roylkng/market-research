"""Archive official NSE 2026-10-19 Muhurat circular and seal amended H20 clock.

Never backdate the PDF's *actual retrieval* time. On HTTP failures retain
a blocked source attempt rather than manufacturing a special-session receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p004_a1_muhurat import (
    AMENDMENT_PATH,
    PDF_DIR,
    SOURCE_URL,
    build_amendment,
    validate_amendment,
    validate_original_nse_circular,
)

RECEIPT_ID = "HG009-P004-A1-NSE-CIRCULAR-RECEIPT-v1"


def _save_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise AlphaContractError(f"A1 evidence cannot be overwritten: {path}")
        return
    path.write_bytes(raw)


def _load_report(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AlphaContractError("A1 original report not JSON object")
    return data


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", default="local")
    p.add_argument("--check", action="store_true")
    p.add_argument("--receipt", type=Path)
    return p.parse_args()


def main() -> int:
    args = _args()
    root = args.repo_root
    if args.check:
        if args.receipt is None:
            raise SystemExit("A1 --check requires an exact source receipt path")
        from marketlab.hg009_p004_a1_muhurat import materialize_amendment

        expected = materialize_amendment(root, args.receipt)
        existing = _load_report(root / AMENDMENT_PATH)
        validate_amendment(existing, root=root, receipt_path=args.receipt)
        if existing != expected:
            raise AlphaContractError("A1 original MuHURAT amendment not reproducible")
        print(json.dumps({
            "state": "ORIGINAL_NSE_SOURCE_REPLAY_VERIFIED",
            "amendment_sha256": existing["amendment_sha256"],
            "H20_last_session": existing["amended_H20_last_session"],
            "economic_returns_calculated": False,
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0

    if not args.run_id or "/" in args.run_id or ".." in args.run_id:
        raise AlphaContractError("A1 run-id must be a filename-safe identifier")
    already = root / AMENDMENT_PATH
    if already.is_file():
        from marketlab.hg009_p004_a1_muhurat import validate_amendment

        preserved = _load_report(already)
        matched = []
        for receipt_file in sorted((root / PDF_DIR / "attempts").glob("*.json")):
            attempt = _load_report(receipt_file)
            if attempt.get("receipt_sha256") == preserved.get(
                "original_receipt_sha256"
            ):
                matched.append(receipt_file)
        if len(matched) != 1:
            raise AlphaContractError("A1 immutable original source receipt ambiguous")
        validate_amendment(
            preserved,
            root=root,
            receipt_path=matched[0].relative_to(root),
        )
        print(json.dumps({
            "state": "ORIGINAL_NSE_SOURCE_ALREADY_SEALED_AND_VERIFIED",
            "source_sha256": preserved["original_source_pdf_sha256"],
            "amendment_sha256": preserved["amendment_sha256"],
            "H20_amended_exit": preserved["amended_H20_last_session"],
            "new_source_attempt_created": False,
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0
    observed_at = datetime.now(UTC).isoformat()
    attempt = {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "source_url": SOURCE_URL,
        "captured_at_utc": observed_at,
        "source_state": "BLOCKED_ORIGINAL_NSE_HTTP",
        "actual_http_status": None,
        "error_class": None,
        "original_pdf_sha256": None,
        "original_pdf_repo_path": None,
        "original_circular_proof": None,
        "live_capital_allowed": False,
    }
    raw = None
    try:
        answer = requests.get(
            SOURCE_URL,
            headers={
                "Accept": "application/pdf",
                "User-Agent": "Mozilla/5.0 MarketLabResearch",
            },
            timeout=30,
            allow_redirects=False,
        )
        observed_at = datetime.now(UTC).isoformat()
        attempt["captured_at_utc"] = observed_at
        attempt["actual_http_status"] = answer.status_code
        if answer.status_code == 200:
            raw = answer.content
    except requests.RequestException as exc:
        attempt["error_class"] = type(exc).__name__
        attempt["error_detail"] = str(exc)[:600]
        attempt["captured_at_utc"] = datetime.now(UTC).isoformat()
    if raw is not None:
        try:
            verified = validate_original_nse_circular(raw)
        except AlphaContractError as exc:
            attempt["source_state"] = "BLOCKED_ORIGINAL_NSE_PDF_CONTENT"
            attempt["error_class"] = type(exc).__name__
            attempt["error_detail"] = str(exc)[:600]
            attempt["original_pdf_sha256"] = hashlib.sha256(raw).hexdigest()
            # Original bytes are retained as QUARANTINE only. They are never
            # accepted as a verified circular or scientific calendar proof.
            quarantined = PDF_DIR / "quarantine" / (
                f"unverified-CMTR76941-{attempt['original_pdf_sha256']}.pdf"
            )
            _save_once(root / quarantined, raw)
            attempt["quarantine_original_pdf_repo_path"] = str(quarantined)
        else:
            source_path = PDF_DIR / (
                f"CMTR76941-{verified['raw_sha256']}.pdf"
            )
            _save_once(root / source_path, raw)
            attempt.update({
                "source_state": "ORIGINAL_CIRCULAR_ARCHIVED",
                "original_pdf_sha256": verified["raw_sha256"],
                "original_pdf_repo_path": str(source_path),
                "original_circular_proof": verified,
                "error_class": None,
            })
    attempt["receipt_sha256"] = digest(attempt)
    receipt_path = PDF_DIR / "attempts" / f"{args.run_id}.json"
    _save_once(
        root / receipt_path,
        (json.dumps(attempt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    if attempt["source_state"] != "ORIGINAL_CIRCULAR_ARCHIVED":
        print(json.dumps({
            "state": attempt["source_state"],
            "source_http_status": attempt["actual_http_status"],
            "reason": attempt.get("error_detail"),
            "receipt_path": str(receipt_path),
            "H20_unblocked": False,
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0

    manifest = build_amendment(root=root, receipt=attempt, original_pdf=raw)
    _save_once(
        root / AMENDMENT_PATH,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    validate_amendment(manifest, root=root, receipt_path=receipt_path)
    print(json.dumps({
        "state": "OFFICIAL_SESSION_AMENDMENT_SOURCE_SEALED_LOCALLY",
        "source_sha256": attempt["original_pdf_sha256"],
        "source_receipt_path": str(receipt_path),
        "amendment_sha256": manifest["amendment_sha256"],
        "H20_original_exit": "2026-11-13",
        "H20_amended_exit": manifest["amended_H20_last_session"],
        "dividend_adjusted_or_trade_fills_calculated": False,
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
