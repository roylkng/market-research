from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.gf001_governance import (
    GF001GovernanceError,
    build_full_governance_panel,
    parse_current_governance_xbrl,
)
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    fetch_xbrl,
    sha256_bytes,
    xbrl_session,
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root: Path, raw: bytes) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / "xbrl" / "sha256" / f"{sha}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"GF001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _fetch_parse(
    *,
    session,
    raw_dir: Path,
    symbol: str,
    source: dict,
    timeout_seconds: float,
    attempts: int,
) -> dict:
    url = str(source["xbrl_url"])
    report_date = str(source["report_date"])
    try:
        response = fetch_xbrl(
            session,
            url=url,
            timeout=timeout_seconds,
            attempts=attempts,
        )
        raw = response.content
        sha, path = _retain(raw_dir, raw)
        governance = parse_current_governance_xbrl(
            raw,
            symbol=symbol,
            report_date=report_date,
            source_url=url,
        )
        if governance["raw_sha256"] != sha:
            raise GF001GovernanceError("raw SHA mismatch")
        return {
            "symbol": symbol,
            "status": "READY",
            "source": source,
            "raw_sha256": sha,
            "raw_path": path,
            "governance": governance,
            "error": None,
        }
    except (H023AcquisitionError, GF001GovernanceError) as exc:
        return {
            "symbol": symbol,
            "status": "FAILED",
            "source": source,
            "raw_sha256": None,
            "raw_path": None,
            "governance": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--d002-census", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.02)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    d002 = _load(args.d002_census)
    rows = d002.get("rows")
    if not isinstance(rows, list):
        raise TypeError("GF001 D002 source rows must be a list")

    api = xbrl_session()
    latest_results = []
    prior_results = []
    ready_rows = [row for row in rows if row.get("source_state") == "READY"]
    total = len(ready_rows)

    for index, row in enumerate(ready_rows, start=1):
        symbol = str(row["symbol"]).upper()
        latest = row.get("latest")
        if not isinstance(latest, dict):
            raise TypeError(f"{symbol}: latest source must be an object")
        latest_results.append(
            _fetch_parse(
                session=api,
                raw_dir=args.raw_dir,
                symbol=symbol,
                source=latest,
                timeout_seconds=args.timeout_seconds,
                attempts=args.attempts,
            )
        )

        prior = row.get("prior")
        if row.get("has_adjacent_prior") is True:
            if not isinstance(prior, dict):
                raise TypeError(f"{symbol}: adjacent prior source is unavailable")
            prior_results.append(
                _fetch_parse(
                    session=api,
                    raw_dir=args.raw_dir,
                    symbol=symbol,
                    source=prior,
                    timeout_seconds=args.timeout_seconds,
                    attempts=args.attempts,
                )
            )

        if index == 1 or index % 50 == 0 or index == total:
            latest_status = latest_results[-1]["status"]
            print(
                f"[governance] {index:04d}/{total} {symbol} latest={latest_status}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    panel = build_full_governance_panel(
        d002_census=d002,
        latest_results=latest_results,
        prior_results=prior_results,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "gf001-d002-panel.json").write_text(
        json.dumps(panel, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary = {key: value for key, value in panel.items() if key != "rows"}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
