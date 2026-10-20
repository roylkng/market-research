"""Source/archive authenticated GESHIP cancellation and Oct19 purchase PDFs.

The issuer dailyreport.pdf URL can be overwritten with a newer trading day.
A different date is an explicit BLOCKED source, never rewritten as Oct19.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p024_geship_buyback import (
    EVIDENCE,
    build_geship_capital_bridge,
    make_source_receipt,
    validate_bridge,
)

ORIGINALS = Path("research/l001/originals/geship_buyback")
REPORT = Path("research/l001/l001-p024-geship-buyback-capital-bridge-v1.json")


def _save_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_bytes() != data:
            raise AlphaContractError(f"P024 sealed file collision: {path}")
        return
    path.write_bytes(data)


def _download(url: str) -> tuple[int, bytes | None]:
    if url not in {item["url"] for item in EVIDENCE.values()}:
        raise AlphaContractError("P024 disallowed moving issuer URL")
    res = requests.get(
        url,
        headers={"Accept": "application/pdf", "User-Agent": "Mozilla/5.0"},
        timeout=35,
        allow_redirects=False,
    )
    return res.status_code, res.content if res.status_code == 200 else None


def load_sealed(root: Path, report: dict) -> tuple[dict[str, bytes], dict[str, dict]]:
    orig, receipts = {}, {}
    for kind in EVIDENCE:
        receipt = report["issuer_source_custody"][kind]
        raw_path = root / receipt["original_raw_path"]
        original = raw_path.read_bytes()
        orig[kind] = original
        receipts[kind] = receipt
    return orig, receipts


def _run(root: Path, run_id: str) -> dict:
    if not run_id or any(s in run_id for s in ("/", "..", "\\")):
        raise AlphaContractError("P024 unsafe source attempt identity")
    published = root / REPORT
    if published.is_file():
        old = json.loads(published.read_text("utf-8"))
        originals, receipts = load_sealed(root, old)
        validate_bridge(old, originals=originals, receipts=receipts)
        return {
            "state": "SEALED_SOURCE_ALREADY_REPLAYABLE",
            "bridge_sha256": old["report_sha256"],
            "new_evidence_created": False,
            "live_capital_allowed": False,
        }
    records: dict[str, dict] = {}
    raw_pdfs = {}
    for kind, spec in EVIDENCE.items():
        observed = datetime.now(UTC).isoformat()
        original = None
        status = None
        problem = None
        try:
            status, original = _download(spec["url"])
            observed = datetime.now(UTC).isoformat()
        except requests.RequestException as exc:
            observed = datetime.now(UTC).isoformat()
            problem = type(exc).__name__
        receipt: dict = {
            "document_kind": kind,
            "source_url": spec["url"],
            "first_actual_source_retrieval_utc": observed,
            "http_status": status,
            "raw_sha256": None,
            "original_raw_repo_path": None,
            "state": "BLOCKED_ORIGINAL_ISSUER_HTTP",
            "error_class": problem,
            "live_capital_allowed": False,
        }
        if status == 200 and original is not None:
            try:
                proof = make_source_receipt(
                    kind, original, retrieved_at_utc=observed
                )
            except AlphaContractError as exc:
                receipt["state"] = "BLOCKED_ORIGINAL_DATE_OR_ISSUER_PDF"
                receipt["error_class"] = type(exc).__name__
                receipt["error_detail"] = str(exc)[:300]
            else:
                _save_once(root / proof["original_raw_path"], original)
                raw_pdfs[kind] = original
                records[kind] = proof
                receipt["state"] = "ORIGINAL_ISSUER_PDF_ARCHIVED"
                receipt["raw_sha256"] = proof["original_pdf_sha256"]
                receipt["original_raw_repo_path"] = proof["original_raw_path"]
                receipt["proof_receipt_sha256"] = proof["receipt_sha256"]
                receipt["error_class"] = None
        receipt["attempt_sha256"] = digest(receipt)
        _save_once(
            root / ORIGINALS / "attempts" / f"{run_id}-{kind}.json",
            (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
        )
    if set(records) != set(EVIDENCE):
        return {
            "state": "PENDING_ORIGINAL_BUYBACK_CUSTODY",
            "received": sorted(records),
            "missing": sorted(set(EVIDENCE) - set(records)),
            "new_evidence_created": bool(records),
            "live_capital_allowed": False,
        }
    result = build_geship_capital_bridge(raw_pdfs, records)
    validate_bridge(result, originals=raw_pdfs, receipts=records)
    _save_once(
        published,
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode(),
    )
    return {
        "state": "NEW_ORIGINAL_GESHIP_SOURCE_BRIDGE_SEALED",
        "bridge_sha256": result["report_sha256"],
        "post_september_certified_shares": (
            result["certified_post_september_paidup_shares"]
        ),
        "october_19_cumulative_purchased_shares": (
            result["oct19_issuer_report_total_cumulative_purchased"]
        ),
        "later_legal_cancellation_verified": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--run-id", default="local")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.check:
        path = args.repo_root / REPORT
        if not path.is_file():
            print(json.dumps({
                "state": "ORIGINAL_ISSUER_BRIDGE_NOT_SEALED",
                "live_capital_allowed": False,
            }, sort_keys=True))
            return 0
        report = json.loads(path.read_text("utf-8"))
        originals, receipts = load_sealed(args.repo_root, report)
        validate_bridge(report, originals=originals, receipts=receipts)
        print(json.dumps({
            "state": "ORIGINAL_ISSUER_BUYBACK_PDF_REPLAY_VERIFIED",
            "bridge_sha256": report["report_sha256"],
            "live_capital_allowed": False,
        }, sort_keys=True))
        return 0
    print(json.dumps(_run(args.repo_root, args.run_id), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
