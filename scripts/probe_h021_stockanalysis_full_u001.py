from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from marketlab.h021_stockanalysis_full_probe import (
    build_batch_targets,
    summarize_probe_rows,
    validate_full_probe_config,
)
from marketlab.h021_stockanalysis_parser import (
    financials_url,
    forecast_url,
    parse_annual_forecast,
)
from marketlab.h021_stockanalysis_probe import ROBOTS_URL, robots_allows


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_gzip_json(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"expected gzip JSON object: {path}")
    return payload


def _http_summary(response: requests.Response) -> dict:
    return {
        "status_code": response.status_code,
        "final_url": response.url,
        "content_length": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
    }


def _fetch(
    session: requests.Session,
    *,
    url: str,
    timeout: float,
    robots_text: str,
    user_agent: str,
) -> tuple[requests.Response | None, dict]:
    if not robots_allows(robots_text, user_agent, url):
        return None, {"state": "ROBOTS_BLOCKED", "requested_url": url}
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return None, {
            "state": "REQUEST_ERROR",
            "requested_url": url,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return response, {"state": "HTTP", "requested_url": url, **_http_summary(response)}


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    config = _load_json(args.config)
    errors = validate_full_probe_config(config)
    if errors:
        raise SystemExit(json.dumps({"config_errors": errors}, indent=2))
    if args.batch_id not in config["batch_ids"]:
        raise SystemExit(f"unknown frozen batch: {args.batch_id}")

    anchor = _load_gzip_json(Path(config["anchor_path"]))
    universe = _load_json(Path(config["universe_path"]))
    batch_spec = _load_json(Path(config["batch_spec_path"]))
    targets = build_batch_targets(anchor, universe, batch_spec, args.batch_id)

    timeout = float(config["timeout_seconds"])
    sleep_seconds = float(config["sleep_seconds_between_requests"])
    user_agent = config["user_agent"]
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
        }
    )

    robots_response = session.get(ROBOTS_URL, timeout=timeout)
    if robots_response.status_code != 200:
        raise SystemExit(f"robots.txt returned HTTP {robots_response.status_code}")
    robots_text = robots_response.text

    rows: list[dict] = []
    for index, target in enumerate(targets):
        symbol = target["symbol"]
        forecast_source = forecast_url(symbol)
        financials_source = financials_url(symbol)
        row = {
            **target,
            "forecast_source_url": forecast_source,
            "financials_source_url": financials_source,
            "state": "UNPROCESSED",
            "parser_pass": False,
            "semantic_match_pass": False,
            "probe_pass": False,
        }

        forecast_response, forecast_http = _fetch(
            session,
            url=forecast_source,
            timeout=timeout,
            robots_text=robots_text,
            user_agent=user_agent,
        )
        row["forecast_http"] = forecast_http
        _sleep(sleep_seconds)

        financials_response, financials_http = _fetch(
            session,
            url=financials_source,
            timeout=timeout,
            robots_text=robots_text,
            user_agent=user_agent,
        )
        row["financials_http"] = financials_http

        if forecast_response is None:
            row["state"] = f"FORECAST_{forecast_http['state']}"
        elif forecast_response.status_code != 200:
            row["state"] = f"FORECAST_HTTP_{forecast_response.status_code}"
        else:
            financials_html = (
                financials_response.content
                if financials_response is not None and financials_response.status_code == 200
                else None
            )
            financials_source_for_parser = (
                financials_source if financials_html is not None else None
            )
            try:
                parsed = parse_annual_forecast(
                    symbol=symbol,
                    source_url=forecast_source,
                    html=forecast_response.content,
                    expected_fiscal_period=target["anchor_fiscal_period"],
                    expected_period_ending=target["anchor_period_ending"],
                    financials_html=financials_html,
                    financials_source_url=financials_source_for_parser,
                )
            except (TypeError, ValueError) as exc:
                row.update(
                    {
                        "state": "PARSE_ERROR",
                        "parse_error_type": type(exc).__name__,
                        "parse_error": str(exc),
                    }
                )
            else:
                semantic_match = parsed.eps_currency == target["anchor_eps_currency"]
                row.update(
                    {
                        "state": "PARSED",
                        "parser_pass": True,
                        "semantic_match_pass": semantic_match,
                        "probe_pass": semantic_match,
                        "parsed": parsed.to_dict(),
                        "eps_currency_matches_anchor": semantic_match,
                    }
                )

        rows.append(row)
        if index + 1 < len(targets):
            _sleep(sleep_seconds)

    report = {
        "schema_version": 1,
        "hypothesis_id": "H021-STOCKANALYSIS-FULL-U001-PROBE",
        "captured_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "config_path": str(args.config),
        "batch_id": args.batch_id,
        "robots": {
            "status_code": robots_response.status_code,
            "content_length": len(robots_response.content),
            "sha256": hashlib.sha256(robots_response.content).hexdigest(),
        },
        "summary": summarize_probe_rows(rows),
        "rows": rows,
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"batch={args.batch_id} total={report['summary']['total']} "
        f"pass={report['summary']['probe_pass']} out={args.out}"
    )


if __name__ == "__main__":
    main()
