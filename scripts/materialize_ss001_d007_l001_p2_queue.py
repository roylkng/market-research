from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_d007_chronology_queue import build_p2_queue


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q002", type=Path, required=True)
    parser.add_argument("--d003", type=Path, required=True)
    parser.add_argument("--p1-run", type=Path, required=True)
    parser.add_argument("--documents-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def read_document(document_id: str) -> dict:
        return _load(args.documents_dir / f"{document_id}.json")

    queue = build_p2_queue(
        q002=_load(args.q002),
        d003=_load(args.d003),
        p1_run=_load(args.p1_run),
        read_document=read_document,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            queue,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "queue_id": queue["queue_id"],
                "queue_sha256": queue["queue_sha256"],
                "issuer_count": queue["issuer_count"],
                "announcement_reference_count": queue["announcement_reference_count"],
                "corporate_action_row_count": queue["corporate_action_row_count"],
                "distinct_document_count": queue["distinct_document_count"],
                "p1_reuse_document_count": queue["p1_reuse_document_count"],
                "fresh_document_count": queue["fresh_document_count"],
                "fresh_request_count": queue["fresh_request_count"],
                "shard_request_counts": queue["shard_request_counts"],
                "feasibility_pass": queue["feasibility_pass"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
