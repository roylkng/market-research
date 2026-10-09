from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.ss002_p006_casebook import build_p006_casebook


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"JSON must be an object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p003-corpus", type=Path, required=True)
    parser.add_argument("--p003-documents", type=Path, required=True)
    parser.add_argument("--p004-pilot", type=Path, required=True)
    parser.add_argument("--p005-gate", type=Path, required=True)
    parser.add_argument("--hg001-router", type=Path, required=True)
    parser.add_argument("--ha001-panel", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    pilot = _load(args.p004_pilot)
    cases = pilot.get("cases")
    if not isinstance(cases, list):
        raise TypeError("P004 cases must be a list")
    docs = {}
    for row in cases:
        document_id = row["document_id"]
        docs[document_id] = _load(args.p003_documents / f"{document_id}.json")

    result = build_p006_casebook(
        p003_corpus=_load(args.p003_corpus),
        p003_documents=docs,
        p004_pilot=pilot,
        p005_gate=_load(args.p005_gate),
        hg001_router=_load(args.hg001_router),
        ha001_panel=_load(args.ha001_panel),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(
        f"pack={result['pack_id']} cases={result['case_count']} "
        f"explicit_facts={result['explicit_fact_count']} "
        f"cited_segment_refs={result['cited_segment_reference_count']}"
    )


if __name__ == "__main__":
    main()
