from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg003_l002 import build_company_event_synthesis


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON object required: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--l001-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    synthesis = build_company_event_synthesis(
        selection=_load(args.selection),
        l001_run=_load(args.l001_run),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg003-l002-synthesis.json").write_text(
        json.dumps(
            synthesis,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in synthesis.items() if key != "rows"}
    summary["company_states"] = [
        {
            "symbol": row["symbol"],
            "company_catalyst_state": row["company_catalyst_state"],
            "direct_active_cluster_count": row["direct_active_cluster_count"],
            "completed_direct_cluster_count": row["completed_direct_cluster_count"],
            "indirect_or_context_cluster_count": row[
                "indirect_or_context_cluster_count"
            ],
            "text_pending_thread_count": row["text_pending_thread_count"],
            "latest_clusters": [
                {
                    "semantic_cluster": cluster["semantic_cluster"],
                    "latest_thread_id": cluster["latest_thread_id"],
                    "relevance_group": cluster["relevance_group"],
                    "stage_group": cluster["stage_group"],
                    "latest_transaction_stage": cluster[
                        "latest_transaction_stage"
                    ],
                }
                for cluster in row["clusters"]
            ],
        }
        for row in synthesis["rows"]
    ]
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
