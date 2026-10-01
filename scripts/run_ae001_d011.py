from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from marketlab.alpha import digest
from marketlab.alpha_d011 import (
    D011_REPORT_DATES,
    build_d011_result,
    first_current_source,
    prior_source_at_current_broadcast,
    sample_symbols,
)
from marketlab.h023_acquisition import (
    H023AcquisitionError,
    build_xbrl_evidence,
    discover_standard_quarter_sources,
    fetch_master,
    fetch_xbrl,
    master_session,
    sha256_bytes,
    xbrl_session,
)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _selected_sources(
    sources_by_symbol: dict[str, list[dict]],
) -> dict[str, dict]:
    selected = {}
    for sources in sources_by_symbol.values():
        for report_date in D011_REPORT_DATES:
            current, ambiguous = first_current_source(
                sources,
                report_date=report_date,
            )
            if current is None or ambiguous:
                continue
            selected[str(current["source_id"])] = current
            if report_date == D011_REPORT_DATES[0]:
                continue
            prior, prior_ambiguous = prior_source_at_current_broadcast(
                sources,
                current_report_date=report_date,
                current_broadcast_at_utc=str(
                    current["broadcast_at_utc"]
                ),
            )
            if prior is not None and not prior_ambiguous:
                selected[str(prior["source_id"])] = prior
    return dict(sorted(selected.items()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen AE001 D011 NSE ownership source feasibility"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = _load_json(args.universe)
    symbols = sample_symbols(universe)
    output = args.output
    master_raw_dir = output / "raw" / "master"
    xbrl_raw_dir = output / "raw" / "xbrl"
    master_raw_dir.mkdir(parents=True, exist_ok=True)
    xbrl_raw_dir.mkdir(parents=True, exist_ok=True)

    master_client = master_session(args.timeout_seconds)
    master_status = {}
    sources_by_symbol = {}

    for index, symbol in enumerate(symbols, start=1):
        try:
            response = fetch_master(
                master_client,
                symbol=symbol,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            raw = response.content
            raw_sha = sha256_bytes(raw)
            (master_raw_dir / f"{symbol}-{raw_sha}.json").write_bytes(raw)
            payload = response.json()
            sources = discover_standard_quarter_sources(
                payload,
                symbol=symbol,
            )
            master_status[symbol] = {
                "status": "READY",
                "raw_sha256": raw_sha,
                "source_count": len(sources),
            }
            sources_by_symbol[symbol] = sources
        except (H023AcquisitionError, ValueError, TypeError) as exc:
            master_status[symbol] = {
                "status": "FAILED",
                "raw_sha256": None,
                "source_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
            sources_by_symbol[symbol] = []
        print(
            json.dumps(
                {
                    "phase": "MASTER",
                    "index": index,
                    "total": len(symbols),
                    "symbol": symbol,
                    "status": master_status[symbol]["status"],
                    "source_count": master_status[symbol]["source_count"],
                },
                sort_keys=True,
            )
        )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    selected = _selected_sources(sources_by_symbol)
    evidence = {}
    filing_client = xbrl_session()
    selected_values = list(selected.values())
    for index, source in enumerate(selected_values, start=1):
        source_id = str(source["source_id"])
        try:
            response = fetch_xbrl(
                filing_client,
                url=str(source["xbrl_url"]),
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            raw = response.content
            raw_sha = sha256_bytes(raw)
            (xbrl_raw_dir / f"{source_id}-{raw_sha}.xml").write_bytes(raw)
            evidence[source_id] = build_xbrl_evidence(source, raw)
        except H023AcquisitionError as exc:
            evidence[source_id] = {
                "status": "FETCH_FAILED",
                "source_id": source_id,
                "xbrl_sha256": None,
                "mutual_fund_percentage": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        print(
            json.dumps(
                {
                    "phase": "XBRL",
                    "index": index,
                    "total": len(selected_values),
                    "symbol": source["symbol"],
                    "report_date": source["report_date"],
                    "status": evidence[source_id]["status"],
                },
                sort_keys=True,
            )
        )
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    result = build_d011_result(
        universe=universe,
        master_status_by_symbol=master_status,
        sources_by_symbol=sources_by_symbol,
        evidence_by_source_id=evidence,
    )

    manifest = {
        "schema_version": 1,
        "diagnostic_id": "AE001-D011-v1",
        "universe_path": str(args.universe),
        "universe_sha256": digest(universe),
        "sample_symbols": list(symbols),
        "master_status_by_symbol": master_status,
        "sources_by_symbol": sources_by_symbol,
        "selected_sources_by_id": selected,
        "evidence_by_source_id": evidence,
        "selected_unique_source_count": len(selected),
        "return_labels_opened": False,
        "model_fit_performed": False,
        "live_capital_allowed": False,
    }
    manifest["manifest_sha256"] = digest(manifest)

    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "source-manifest.json", manifest)
    _write_json(output / "result.json", result)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key != "observations"
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
