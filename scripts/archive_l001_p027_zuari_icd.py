"""Capture September 2026 Zuari Agro ICD repayment original issuer PDFs.

Both signed original PDFs are necessary for a source-backed debt/cash bridge.
A network block is a factual missingness receipt, never inferred wealth.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p027_zuari_icd import (
    EVIDENCE,
    FRONTIER_BLOB,
    FRONTIER_PATH,
    build_parent_icd_cash_bridge,
    make_receipt,
    validate_bridge,
)

ORIGINAL_ROOT = Path("research/l001/originals/zuari_icd")
REPORT = Path("research/l001/l001-p027-zuari-original-icd-cash-bridge-v1.json")


def _blob(raw: bytes) -> str:
    import hashlib
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _save_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != raw:
            raise AlphaContractError("P027 immutable original source path collision")
        return
    path.write_bytes(raw)


def _download(url: str) -> tuple[int, bytes | None]:
    if url not in {spec["url"] for spec in EVIDENCE.values()}:
        raise AlphaContractError("P027 original URL not frozen")
    response = requests.get(
        url,
        timeout=35,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"},
        allow_redirects=False,
    )
    return (
        response.status_code,
        response.content if response.status_code == 200 else None,
    )


def _load_frontier(root: Path) -> dict:
    raw = (root / FRONTIER_PATH).read_bytes()
    if _blob(raw) != FRONTIER_BLOB:
        raise AlphaContractError("P027 original P023 source Git blob altered")
    return json.loads(raw)


def _stored_sources(root: Path, report: dict) -> tuple[dict, dict]:
    raw_by_kind, receipts = {}, {}
    for kind in EVIDENCE:
        receipt = report["original_issuer_source_documents"][kind]
        raw_by_kind[kind] = (
            root / receipt["original_raw_path"]
        ).read_bytes()
        receipts[kind] = receipt
    return raw_by_kind, receipts


def _run(root: Path, *, run_id: str) -> dict:
    if not run_id or any(c in run_id for c in ("/", "\\", "..")):
        raise AlphaContractError("P027 run ID contains unsafe filename")
    previous = root / REPORT
    if previous.is_file():
        old = json.loads(previous.read_text(encoding="utf-8"))
        raw, receipts = _stored_sources(root, old)
        validate_bridge(
            old, originals=raw, receipts=receipts,
            earlier_frontier=_load_frontier(root),
        )
        return {
            "state": "ORIGINAL_ZUARI_ICD_SOURCE_ALREADY_REPLAY_VERIFIED",
            "sha": old["report_sha256"],
            "changed": False,
            "live_capital_allowed": False,
        }
    receipts = {}
    raw_by_kind = {}
    statuses = {}
    for kind, spec in EVIDENCE.items():
        status, raw, error = None, None, None
        try:
            status, raw = _download(spec["url"])
        except requests.RequestException as exc:
            error = type(exc).__name__
        captured = datetime.now(UTC).isoformat()
        attempt = {
            "kind": kind,
            "url": spec["url"],
            "captured_at_utc": captured,
            "http_status": status,
            "state": "BLOCKED_HTTP",
            "raw_sha256": None,
            "original_raw_path": None,
            "error_class": error,
            "live_capital_allowed": False,
        }
        if status == 200 and raw is not None:
            try:
                record = make_receipt(kind, raw, captured_at_utc=captured)
            except AlphaContractError as exc:
                attempt["state"] = "BLOCKED_ISSUER_DATE_OR_CONTENT"
                attempt["raw_sha256"] = None
                attempt["error_class"] = type(exc).__name__
                attempt["error_excerpt"] = str(exc)[:200]
            else:
                _save_once(root / record["original_raw_path"], raw)
                raw_by_kind[kind] = raw
                receipts[kind] = record
                attempt["state"] = "ORIGINAL_ISSUER_PDF_ARCHIVED"
                attempt["raw_sha256"] = record["raw_pdf_sha256"]
                attempt["original_raw_path"] = record["original_raw_path"]
                attempt["error_class"] = None
        attempt["attempt_sha256"] = digest(attempt)
        _save_once(
            root / ORIGINAL_ROOT / "attempts" / (run_id + "-" + kind + ".json"),
            (json.dumps(attempt, sort_keys=True, indent=2) + "\n").encode(),
        )
        statuses[kind] = attempt["state"]
    if set(receipts) != set(EVIDENCE):
        return {
            "state": "ORIGINAL_ZUARI_ISSUER_SOURCE_INCOMPLETE",
            "source_states": statuses,
            "source_completed_count": len(receipts),
            "new_valuation_or_buy_rating": False,
            "live_capital_allowed": False,
        }
    result = build_parent_icd_cash_bridge(
        raw_by_kind, receipts, earlier_frontier=_load_frontier(root)
    )
    validate_bridge(
        result, originals=raw_by_kind, receipts=receipts,
        earlier_frontier=_load_frontier(root),
    )
    _save_once(
        root / REPORT,
        (json.dumps(result, sort_keys=True, indent=2) + "\n").encode(),
    )
    return {
        "state": "ORIGINAL_ZUARI_258_50CR_PRINCIPAL_REPAYMENT_VERIFIED",
        "source_states": statuses,
        "total_repayment_cr": result[
            "issuer_published_ICD_parent_creditor_cash_event"
        ]["total_principal_icd_repaid_cr"],
        "new_parent_equity_value_from_existing_loan_repayment_cr": 0,
        "sha": result["report_sha256"],
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.repo_root
    if args.check:
        file = root / REPORT
        if not file.is_file():
            print(json.dumps({
                "state": "ORIGINAL_ZUARI_ICD_PDFS_NOT_BOTH_SEALED",
                "live_capital_allowed": False,
            }, sort_keys=True))
            return 0
        obj = json.loads(file.read_text(encoding="utf-8"))
        originals, receipts = _stored_sources(root, obj)
        validate_bridge(
            obj, originals=originals, receipts=receipts,
            earlier_frontier=_load_frontier(root),
        )
        print(json.dumps({
            "state": "ORIGINAL_ZUARI_ICD_PDFS_FULLY_REPLAYED",
            "sha": obj["report_sha256"],
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0
    print(json.dumps(_run(root, run_id=args.run_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
