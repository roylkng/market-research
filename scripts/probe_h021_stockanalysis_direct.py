from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.h021_stockanalysis_probe import (
    REQUIRED_TEXT_MARKERS,
    ROBOTS_URL,
    audit_legacy_snapshot_semantics,
    forecast_url,
    inspect_forecast_page,
    robots_allows,
)


def _load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("probe config must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("probe config schema_version must equal 1")
    if payload.get("hypothesis_id") != "H021-DIRECT-SOURCE-PROBE":
        raise ValueError("unexpected probe hypothesis_id")
    if payload.get("outcomes_opened") is not False:
        raise ValueError("probe config outcomes_opened must be false")
    if payload.get("live_capital_allowed") is not False:
        raise ValueError("probe config live_capital_allowed must be false")
    if payload.get("robots_url") != ROBOTS_URL:
        raise ValueError("probe must use frozen StockAnalysis robots URL")
    if tuple(payload.get("required_text_markers", [])) != REQUIRED_TEXT_MARKERS:
        raise ValueError("probe required markers differ from frozen inspector")
    symbols = payload.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("probe symbols must be a non-empty list")
    if len(symbols) != len(set(symbols)):
        raise ValueError("probe symbols must be unique")
    legacy_anchor = payload.get("legacy_anchor_path")
    if not isinstance(legacy_anchor, str) or not legacy_anchor.endswith(".json.gz"):
        raise ValueError("legacy_anchor_path must identify the frozen gzip anchor")
    semantic_symbols = payload.get("legacy_semantic_symbols")
    if not isinstance(semantic_symbols, list) or not semantic_symbols:
        raise ValueError("legacy_semantic_symbols must be a non-empty list")
    if len(semantic_symbols) != len(set(semantic_symbols)):
        raise ValueError("legacy_semantic_symbols must be unique")
    return payload


def _captured_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_legacy_anchor(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError("legacy H021 anchor must contain a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = _load_config(args.config)
    user_agent = config["user_agent"]
    timeout = float(config["timeout_seconds"])
    sleep_seconds = float(config["sleep_seconds"])
    legacy_anchor_path = Path(config["legacy_anchor_path"])
    legacy_anchor = _load_legacy_anchor(legacy_anchor_path)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
        }
    )

    report = {
        "schema_version": 1,
        "hypothesis_id": "H021-DIRECT-SOURCE-PROBE",
        "captured_at_utc": _captured_at(),
        "config_path": str(args.config),
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "legacy_anchor_semantics": {
            "path": str(legacy_anchor_path),
            **audit_legacy_snapshot_semantics(
                legacy_anchor,
                config["legacy_semantic_symbols"],
            ),
        },
        "robots": {},
        "pages": [],
        "decision": {},
    }

    try:
        robots_response = session.get(ROBOTS_URL, timeout=timeout)
    except requests.RequestException as exc:
        report["robots"] = {
            "fetch_state": "REQUEST_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        report["decision"] = {
            "direct_primary_retrieval_feasible": False,
            "reason": "robots.txt could not be verified; direct page requests were not attempted",
        }
        _write_report(args.out, report)
        raise SystemExit(2) from exc

    robots_body = robots_response.content
    robots_text = robots_response.text if robots_response.status_code == 200 else ""
    report["robots"] = {
        "fetch_state": "HTTP",
        "status_code": robots_response.status_code,
        "final_url": robots_response.url,
        "content_type": robots_response.headers.get("content-type"),
        "content_length": len(robots_body),
        "sha256": hashlib.sha256(robots_body).hexdigest(),
    }
    if robots_response.status_code != 200:
        report["decision"] = {
            "direct_primary_retrieval_feasible": False,
            "reason": "robots.txt did not return HTTP 200; direct page requests were not attempted",
        }
        _write_report(args.out, report)
        raise SystemExit(2)

    symbols = config["symbols"]
    for index, symbol in enumerate(symbols):
        url = forecast_url(symbol)
        if not robots_allows(robots_text, user_agent, url):
            report["pages"].append(
                {
                    "symbol": symbol,
                    "requested_url": url,
                    "fetch_state": "ROBOTS_BLOCKED",
                    "probe_pass": False,
                }
            )
        else:
            try:
                response = session.get(url, timeout=timeout)
            except requests.RequestException as exc:
                report["pages"].append(
                    {
                        "symbol": symbol,
                        "requested_url": url,
                        "fetch_state": "REQUEST_ERROR",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "probe_pass": False,
                    }
                )
            else:
                row = inspect_forecast_page(
                    symbol=symbol,
                    requested_url=url,
                    status_code=response.status_code,
                    final_url=response.url,
                    content_type=response.headers.get("content-type"),
                    body=response.content,
                )
                row["fetch_state"] = "HTTP"
                report["pages"].append(row)
        if index + 1 < len(symbols) and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    passed = sum(bool(row.get("probe_pass")) for row in report["pages"])
    total = len(report["pages"])
    feasible = total == len(symbols) and passed == total
    report["decision"] = {
        "direct_primary_retrieval_feasible": feasible,
        "passed_pages": passed,
        "total_pages": total,
        "reason": (
            "All frozen public forecast pages were directly retrievable with required markers."
            if feasible
            else "At least one frozen public forecast page failed direct retrieval or marker checks."
        ),
    }
    _write_report(args.out, report)
    print(f"passed={passed}/{total} feasible={feasible} report={args.out}")
    if not feasible:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
