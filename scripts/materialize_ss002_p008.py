from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_p008_source_review import build_p008_source_review


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"source must be a JSON object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p003-corpus", type=Path, required=True)
    parser.add_argument("--p003-documents", type=Path, required=True)
    parser.add_argument("--p006-casebook", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    p006 = _load(args.p006_casebook)
    selected = [
        row
        for row in p006["cases"]
        if row["active_transaction_research_lens"] is True
    ]
    docs = {
        row["document_id"]: _load(args.p003_documents / f"{row['document_id']}.json")
        for row in selected
    }
    result = build_p008_source_review(
        p003_corpus=_load(args.p003_corpus),
        p003_documents=docs,
        p006_casebook=p006,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "pack_sha256": result["pack_sha256"],
        "case_count": result["case_count"],
        "claim_count": result["claim_count"],
        "extracted_page_segment_count": result["extracted_page_segment_count"],
        "empty_page_count": result["empty_page_count"],
        "case_symbols": result["case_symbols"],
        "pages_requiring_visual_review": {
            row["symbol"]: row["original_pages_requiring_visual_review"]
            for row in result["cases"]
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
