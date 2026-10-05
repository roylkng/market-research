from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.hg005_d002a import (
    build_source_corpus,
    resolve_discovery_attachment,
    source_evidence,
    validate_source_manifest,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, *, kind: str, raw: bytes, suffix: str) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / kind / "sha256" / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"HG005 D002A content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = _load(args.manifest)
    sources = validate_source_manifest(manifest)
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    evidence_rows = []

    for index, source in enumerate(sources, start=1):
        source_id = str(source["source_id"])
        resolved_url = None
        discovery_sha = None
        discovery_path = None
        discovery_match = None
        try:
            if source["mode"] == "DIRECT_URL":
                resolved_url = str(source["url"])
            else:
                discovery = source["discovery"]
                payload, discovery_raw = client.corporate_announcements_with_raw(
                    str(source["symbol"]),
                    from_date=str(discovery["from_date"]),
                    to_date=str(discovery["to_date"]),
                )
                discovery_sha, discovery_path = _retain(
                    args.raw_dir,
                    kind="discovery",
                    raw=discovery_raw,
                    suffix=".json",
                )
                discovery_match = resolve_discovery_attachment(
                    source=source,
                    payload=payload,
                )
                resolved_url = str(discovery_match["resolved_url"])

            raw = client.archive_bytes(resolved_url)
            raw_sha, raw_path = _retain(
                args.raw_dir,
                kind="documents",
                raw=raw,
                suffix=".bin",
            )
            row = source_evidence(
                source=source,
                resolved_url=resolved_url,
                raw=raw,
                discovery_raw_sha256=discovery_sha,
                discovery_match=discovery_match,
            )
            if row["raw_sha256"] != raw_sha:
                raise RuntimeError(f"{source_id}: retained raw SHA mismatch")
            row["raw_path"] = raw_path
            row["discovery_raw_path"] = discovery_path
        except (NSEAcquisitionError, RuntimeError, ValueError) as exc:
            row = source_evidence(
                source=source,
                resolved_url=resolved_url,
                raw=None,
                discovery_raw_sha256=discovery_sha,
                discovery_match=discovery_match,
                error=f"{type(exc).__name__}: {exc}",
            )
            row["raw_path"] = None
            row["discovery_raw_path"] = discovery_path

        evidence_rows.append(row)
        print(
            f"[d002a] {index:02d}/{len(sources)} {source_id} "
            f"status={row['status']} text={row['text_state']}",
            flush=True,
        )

    corpus = build_source_corpus(
        manifest=manifest,
        evidence_rows=evidence_rows,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "hg005-d002a-corpus.json").write_text(
        json.dumps(
            corpus,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in corpus.items() if key != "sources"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
