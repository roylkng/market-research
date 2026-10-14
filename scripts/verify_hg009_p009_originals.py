"""Independently verify archived original NSE issuer bytes and actual receipts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p009_originals import (
    ARCHIVE_ROOT,
    source_specifications,
    validate_original_receipt,
)


def verify(root: Path) -> dict:
    sources = {row["document_id"]: row for row in source_specifications(root)}
    archive_root = root / ARCHIVE_ROOT / "attempts"
    statuses = Counter()
    archived = set()
    versions: dict[str, set[str]] = {document_id: set() for document_id in sources}
    checked = []
    for path in sorted(archive_root.glob("*.json")) if archive_root.exists() else []:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise AlphaContractError("P009 original source receipt not JSON object")
        validate_original_receipt(receipt, root=root)
        name = receipt.get("document_id")
        if name not in sources:
            raise AlphaContractError("P009 nonregistered issuer document in source ledger")
        spec = sources[name]
        for key, value in spec.items():
            if receipt.get(key) != value:
                raise AlphaContractError(
                    f"P009 archived source specification changed: {key}"
                )
        statuses[receipt["state"]] += 1
        if receipt.get("raw_repo_path"):
            archived.add(name)
            versions[name].add(receipt["raw_sha256"])
        checked.append({
            "document_id": name,
            "source_sha256": receipt.get("raw_sha256"),
            "retrieval_clock": receipt["actual_retrieved_at_utc"],
            "state": receipt["state"],
        })
    return {
        "program_id": "HG009-P009-ORIGINAL-ISSUER-DOCUMENT-CUSTODY-v1",
        "predeclared_document_count": len(sources),
        "verified_attempt_count": len(checked),
        "unique_archived_document_count": len(archived),
        "original_byte_versions_per_document": {
            name: sorted(values)
            for name, values in sorted(versions.items())
        },
        "issuer_documents_with_multiple_raw_byte_versions": sorted(
            name for name, values in versions.items() if len(values) > 1
        ),
        "different_html_bytes_may_have_different_financial_values": True,
        "no_version_is_silently_promoted": True,
        "retrieval_states": dict(sorted(statuses.items())),
        "receipt_evidence": checked,
        "all_issuer_financial_values_verified": False,
        "shareholder_owner_cashflow_verified": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    args = p.parse_args()
    print(json.dumps(verify(args.repo_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
