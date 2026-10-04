from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.events import sha256_bytes
from marketlab.fa001_schema_audit import (
    FA001SchemaError,
    build_schema_audit,
    parse_schema_inventory,
    select_audit_filings,
)
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, *, kind: str, raw: bytes, url: str) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    suffix = Path(urlparse(url).path).suffix.lower() or ".bin"
    path = root / kind / "sha256" / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"FA001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _filing_state(
    *,
    client: NSEClient,
    candidate,
    raw_dir: Path,
) -> dict:
    if candidate is None:
        return {"status": "UNAVAILABLE", "reason": "NO_EXACT_PERIOD_CANDIDATE"}
    try:
        raw = client.archive_bytes(candidate.source_url)
        sha, path = _retain(
            raw_dir,
            kind="filings",
            raw=raw,
            url=candidate.source_url,
        )
        audit = parse_schema_inventory(raw, candidate=candidate)
        if audit["raw_sha256"] != sha:
            raise FA001SchemaError("filing raw SHA mismatch")
        return {
            "status": "READY",
            "reason": None,
            "candidate": {
                "symbol": candidate.symbol,
                "accounting_basis": candidate.accounting_basis,
                "period_end": candidate.period_end,
                "exchange_published_at_utc": candidate.exchange_published_at_utc,
                "source_url": candidate.source_url,
                "discovery_row_sha256": candidate.discovery_row_sha256,
            },
            "raw_path": path,
            "audit": audit,
        }
    except (NSEAcquisitionError, FA001SchemaError) as exc:
        return {
            "status": "FAILED",
            "reason": f"{type(exc).__name__}: {exc}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.03)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample = _load(args.sample)
    rows = sample.get("symbols")
    if not isinstance(rows, list) or len(rows) != 48:
        raise TypeError("FA001 D001 sample must contain exactly 48 symbol rows")

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    observations = []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise TypeError("FA001 D001 sample row must be an object")
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("FA001 D001 sample row lacks symbol")
        try:
            payload, discovery_raw = client.integrated_financial_filings_with_raw(symbol)
            discovery_sha, discovery_path = _retain(
                args.raw_dir,
                kind="discovery",
                raw=discovery_raw,
                url=NSEClient.INTEGRATED_FILING_ENDPOINT.url,
            )
            annual_candidate, quarter_candidate = select_audit_filings(
                payload,
                symbol=symbol,
            )
            annual = _filing_state(
                client=client,
                candidate=annual_candidate,
                raw_dir=args.raw_dir,
            )
            quarter = _filing_state(
                client=client,
                candidate=quarter_candidate,
                raw_dir=args.raw_dir,
            )
            observations.append(
                {
                    "symbol": symbol,
                    "discovery_raw_sha256": discovery_sha,
                    "discovery_raw_path": discovery_path,
                    "annual": annual,
                    "quarter": quarter,
                }
            )
        except (NSEAcquisitionError, FA001SchemaError) as exc:
            observations.append(
                {
                    "symbol": symbol,
                    "discovery_raw_sha256": None,
                    "discovery_raw_path": None,
                    "annual": {
                        "status": "FAILED",
                        "reason": f"{type(exc).__name__}: {exc}",
                    },
                    "quarter": {
                        "status": "FAILED",
                        "reason": f"{type(exc).__name__}: {exc}",
                    },
                }
            )

        if index == 1 or index % 8 == 0 or index == len(rows):
            current = observations[-1]
            print(
                f"[fa001] {index:02d}/48 {symbol} "
                f"annual={current['annual']['status']} "
                f"quarter={current['quarter']['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    audit = build_schema_audit(
        sample=sample,
        observations=observations,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "fa001-d001-audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in audit.items() if key != "observations"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
