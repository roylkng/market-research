from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.h021_stockanalysis_parser import parse_annual_forecast
from marketlab.h021_stockanalysis_probe import ROBOTS_URL, forecast_url, robots_allows


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_anchor(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError("H021 anchor must contain a JSON object")
    return payload


def _validate_config(config: dict) -> None:
    if config.get("schema_version") != 1:
        raise ValueError("parser probe config schema_version must equal 1")
    if config.get("hypothesis_id") != "H021-STOCKANALYSIS-PARSER-PROBE":
        raise ValueError("unexpected parser probe hypothesis_id")
    if config.get("robots_url") != ROBOTS_URL:
        raise ValueError("parser probe must use frozen StockAnalysis robots URL")
    if config.get("outcomes_opened") is not False:
        raise ValueError("parser probe outcomes_opened must be false")
    if config.get("live_capital_allowed") is not False:
        raise ValueError("parser probe live_capital_allowed must be false")
    symbols = config.get("symbols")
    if not isinstance(symbols, list) or not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("parser probe symbols must be a non-empty unique list")


def _write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = _load_object(args.config)
    _validate_config(config)
    anchor_path = Path(config["anchor_path"])
    anchor = _load_anchor(anchor_path)
    by_symbol = {
        row["symbol"]: row
        for row in anchor.get("observations", [])
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    }
    missing_targets = sorted(set(config["symbols"]) - set(by_symbol))
    if missing_targets:
        raise ValueError(f"parser probe symbols missing from frozen anchor: {missing_targets}")

    timeout = float(config["timeout_seconds"])
    sleep_seconds = float(config["sleep_seconds"])
    user_agent = config["user_agent"]
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
        }
    )

    robots_response = session.get(ROBOTS_URL, timeout=timeout)
    robots_body = robots_response.content
    if robots_response.status_code != 200:
        raise SystemExit(f"robots.txt returned HTTP {robots_response.status_code}")
    robots_text = robots_response.text

    report = {
        "schema_version": 1,
        "hypothesis_id": "H021-STOCKANALYSIS-PARSER-PROBE",
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config_path": str(args.config),
        "anchor_path": str(anchor_path),
        "robots": {
            "status_code": robots_response.status_code,
            "sha256": hashlib.sha256(robots_body).hexdigest(),
            "content_length": len(robots_body),
        },
        "rows": [],
        "decision": {},
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }

    for index, symbol in enumerate(config["symbols"]):
        anchor_row = by_symbol[symbol]
        source_url = forecast_url(symbol)
        result = {
            "symbol": symbol,
            "source_url": source_url,
            "anchor_fiscal_period": anchor_row.get("fiscal_period"),
            "anchor_period_ending": anchor_row.get("period_ending"),
            "anchor_eps_currency": anchor_row.get("eps_currency"),
            "anchor_consensus_eps": anchor_row.get("consensus_eps"),
        }
        if not robots_allows(robots_text, user_agent, source_url):
            result.update({"state": "ROBOTS_BLOCKED", "parser_pass": False})
        else:
            try:
                response = session.get(source_url, timeout=timeout)
            except requests.RequestException as exc:
                result.update(
                    {
                        "state": "REQUEST_ERROR",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "parser_pass": False,
                    }
                )
            else:
                result.update(
                    {
                        "state": "HTTP",
                        "status_code": response.status_code,
                        "content_length": len(response.content),
                        "sha256": hashlib.sha256(response.content).hexdigest(),
                    }
                )
                if response.status_code != 200:
                    result["parser_pass"] = False
                else:
                    try:
                        parsed = parse_annual_forecast(
                            symbol=symbol,
                            source_url=source_url,
                            html=response.content,
                            expected_fiscal_period=anchor_row["fiscal_period"],
                            expected_period_ending=anchor_row["period_ending"],
                        )
                    except (KeyError, TypeError, ValueError) as exc:
                        result.update(
                            {
                                "parser_pass": False,
                                "parse_error_type": type(exc).__name__,
                                "parse_error": str(exc),
                            }
                        )
                    else:
                        result.update(
                            {
                                "parser_pass": True,
                                "parsed": parsed.to_dict(),
                                "eps_currency_matches_anchor": (
                                    parsed.eps_currency == anchor_row.get("eps_currency")
                                ),
                            }
                        )
        report["rows"].append(result)
        if index + 1 < len(config["symbols"]) and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    passed = sum(bool(row.get("parser_pass")) for row in report["rows"])
    total = len(report["rows"])
    report["decision"] = {
        "parser_live_validation_pass": passed == total,
        "passed_rows": passed,
        "total_rows": total,
        "reason": (
            "All frozen parser-probe symbols yielded the exact Sep 11 target period."
            if passed == total
            else "At least one frozen parser-probe symbol did not yield the exact Sep 11 target period."
        ),
    }
    _write(args.out, report)
    print(f"parser_pass={passed}/{total} report={args.out}")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
