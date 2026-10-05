from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg006_evidence import combine_historical_evidence


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d001-census", type=Path, required=True)
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    census = _load(args.d001_census)
    manifest_paths = sorted(args.shards_root.rglob("shard-manifest.json"))
    if len(manifest_paths) != 8:
        raise ValueError(
            f"HG006 S001 combine requires 8 shard manifests, found {len(manifest_paths)}"
        )
    manifests = [_load(path) for path in manifest_paths]

    document_rows = []
    source_paths = {}
    for manifest_path in manifest_paths:
        docs = sorted((manifest_path.parent / "documents").glob("*.json"))
        for path in docs:
            row = _load(path)
            document_rows.append(row)
            url = str(row.get("source_url") or "")
            if not url or url in source_paths:
                raise ValueError("HG006 S001 duplicate/empty source URL document artifact")
            source_paths[url] = path

    corpus = combine_historical_evidence(
        census=census,
        shard_manifests=manifests,
        document_rows=document_rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    out_docs = args.output / "documents"
    out_docs.mkdir(parents=True, exist_ok=True)
    for url, source in sorted(source_paths.items()):
        shutil.copyfile(source, out_docs / source.name)

    (args.output / "hg006-s001-corpus.json").write_text(
        json.dumps(corpus, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in corpus.items()
        if key not in {"chronologies", "documents", "event_states"}
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
