from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.gf001_schema_audit import (
    GF001SchemaError,
    audit_shareholding_xbrl,
    build_schema_audit,
)
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    fetch_xbrl,
    xbrl_session,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, raw: bytes) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / "shareholding-xbrl" / "sha256" / f"{sha}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"GF001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen GF001-D001 current shareholding XBRL schema audit"
    )
    parser.add_argument("--d002-census", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d002 = _load(args.d002_census)
    sample = _load(args.sample)

    rows = d002.get("rows")
    if not isinstance(rows, list):
        raise TypeError("GF001 D002 census rows unavailable")
    by_symbol = {
        str(row.get("symbol") or "").upper(): row
        for row in rows
        if isinstance(row, dict)
    }

    sample_rows = sample.get("symbols")
    if not isinstance(sample_rows, list):
        raise TypeError("GF001 sample symbols unavailable")

    session = xbrl_session()
    filing_results = []

    for index, sample_row in enumerate(sample_rows, start=1):
        symbol = str(sample_row["symbol"]).upper()
        expected_date = str(sample_row["source_report_date"])
        d002_row = by_symbol.get(symbol)
        if not isinstance(d002_row, dict):
            raise RuntimeError(f"{symbol}: absent from D002 census")
        latest = d002_row.get("latest")
        if (
            d002_row.get("source_state") != "READY"
            or not isinstance(latest, dict)
            or latest.get("report_date") != expected_date
        ):
            raise RuntimeError(
                f"{symbol}: D002 latest source does not match frozen sample date"
            )

        url = str(latest["xbrl_url"])
        try:
            response = fetch_xbrl(
                session,
                url=url,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            raw = response.content
            sha, path = _retain(args.raw_dir, raw)
            audit = audit_shareholding_xbrl(
                raw,
                symbol=symbol,
                report_date=expected_date,
                source_url=url,
            )
            if audit["raw_sha256"] != sha:
                raise RuntimeError(f"{symbol}: retained raw hash mismatch")
            filing_results.append(
                {
                    "symbol": symbol,
                    "status": "READY",
                    "raw_sha256": sha,
                    "raw_path": path,
                    "audit": audit,
                    "error": None,
                }
            )
        except (H023AcquisitionError, GF001SchemaError, RuntimeError) as exc:
            filing_results.append(
                {
                    "symbol": symbol,
                    "status": "FAILED",
                    "raw_sha256": None,
                    "raw_path": None,
                    "audit": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        print(
            f"[gf001] {index:02d}/{len(sample_rows)} {symbol} "
            f"status={filing_results[-1]['status']}",
            flush=True,
        )

    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    audit = build_schema_audit(
        d002_census=d002,
        sample=sample,
        filing_results=filing_results,
        captured_at_utc=captured_at,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "gf001-d001-schema-audit.json").write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        key: value
        for key, value in audit.items()
        if key not in {"filings", "concept_file_counts", "context_file_counts"}
    }
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
