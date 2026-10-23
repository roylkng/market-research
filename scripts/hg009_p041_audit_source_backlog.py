"""HG009 P041 exact-identity source backlog auditor. No automatic classification."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "research/hg009/hg009-p030-sector-proof-queue-v1.json"
BACKLOG = REPO / "research/hg009/p041-uncovered-158-original-source-backlog-20261023.csv"
FIELDS = ("arm", "symbol", "isin", "source_url", "source_publication_utc",
          "first_retrieved_utc", "raw_sha256", "classification_status")


def audit(queue_path: Path = QUEUE, backlog_path: Path = BACKLOG) -> dict:
    original = queue_path.read_bytes()
    records = json.loads(original)["future_source_collection_queue"]
    if len(records) != 300:
        raise ValueError("frozen original denominator must equal 300")
    ids = [(r["arm"], r["original_symbol"], r["frozen_isin"]) for r in records]
    if len(set(ids)) != 300 or Counter(r["arm"] for r in records) != {
        "SELECTED": 100, "ONE_LANE": 100, "ZERO_LANE": 100
    }:
        raise ValueError("original arms or identities changed")
    missing = {
        (r["arm"], r["original_symbol"], r["frozen_isin"])
        for r in records if not r["original_exact_index_join"]
    }
    with backlog_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("schema changed")
        rows = list(reader)
    observed = [(r["arm"], r["symbol"], r["isin"]) for r in rows]
    if len(rows) != 158 or len(set(observed)) != 158 or set(observed) != missing:
        raise ValueError("backlog identity mismatch against immutable original queue")
    if any(r["classification_status"] != "UNSOURCED" or
           any(r[f] for f in ("source_url", "source_publication_utc",
                              "first_retrieved_utc", "raw_sha256")) for r in rows):
        raise ValueError("backlog is only a source discovery queue, not evidence")
    return {
        "schema": "HG009-P041-UNSOURCED-v1",
        "original_queue_sha256": hashlib.sha256(original).hexdigest(),
        "backlog_sha256": hashlib.sha256(backlog_path.read_bytes()).hexdigest(),
        "original_denominator": 300,
        "uncovered": 158,
        "by_arm": dict(sorted(Counter(r["arm"] for r in rows).items())),
        "source_verified": 0,
        "new_classification_verified": 0,
        "next_trial_admitted": False,
        "source_coverage_gate": "BLOCKED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--backlog", type=Path, default=BACKLOG)
    args = parser.parse_args()
    print(json.dumps(audit(args.queue, args.backlog), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
