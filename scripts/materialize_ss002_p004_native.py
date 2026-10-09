from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from marketlab.ss002_p004_native import (
    PILOT_DOCUMENT_IDS,
    build_native_pilot,
)


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with zipfile.ZipFile(args.source_artifact) as artifact:
        source = json.loads(artifact.read("ss002-p003-corpus.json"))
        text_by_document = {
            document_id: json.loads(
                artifact.read(f"documents/{document_id}.json")
            )
            for document_id in PILOT_DOCUMENT_IDS
        }
    decisions = _read_json(args.decisions)
    output = build_native_pilot(source, decisions, text_by_document)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    report = {
        key: value for key, value in output.items() if key != "cases"
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
