from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss001_l001_relevance_queue import build_l001_p0_queue


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Document/manifest must be JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q002-pilot", type=Path, required=True)
    parser.add_argument("--d003-manifest", type=Path, required=True)
    parser.add_argument("--d003-documents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_l001_p0_queue(
        q002=_load(args.q002_pilot),
        d003=_load(args.d003_manifest),
        read_document=lambda document_id: _load(
            args.d003_documents / f"{document_id}.json"
        ),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ss001-d007-l001-p0-queue.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in result.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    requests_dir = args.output / "prompts"
    requests_dir.mkdir(parents=True, exist_ok=True)
    for row in result["rows"]:
        if row["selection_state"] != "SELECTED_COMPLETE_DOCUMENT":
            continue
        path = requests_dir / f"{row['issuer_packet_rank']:02d}-{row['symbol']}.json"
        path.write_text(
            json.dumps(
                row["prompt_envelope"],
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
