from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from marketlab.h021_capture import CANONICAL_SOURCE_VERSION, validate_full_capture
from marketlab.h021_capture_draft import build_capture_draft
from marketlab.h021_stockanalysis_acquisition import (
    StructuralSourceDrift,
    anchor_targets,
    finalize_capture,
    identity_unresolved_row,
    no_coverage_row,
    row_from_parser_error,
    source_blocked_row,
    success_row,
)
from marketlab.h021_stockanalysis_parser import (
    financials_url,
    forecast_currency_from_html,
    forecast_url,
    parse_annual_forecast,
)
from marketlab.h021_stockanalysis_probe import ROBOTS_URL, robots_allows

STOCKANALYSIS_HOST = "stockanalysis.com"
ACQUISITION_CONTRACT_PATH = "research/H021_WEEKLY_ACQUISITION_CONTRACT_V1.md"
BLOCKED_HTTP_STATUSES = {401, 403, 405, 429}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _load_gzip_object(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"expected gzip JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _http_summary(response: requests.Response, fetched_at_utc: str) -> dict:
    return {
        "state": "HTTP",
        "fetched_at_utc": fetched_at_utc,
        "status_code": response.status_code,
        "final_url": response.url,
        "content_type": response.headers.get("Content-Type"),
        "content_length": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
    }


def _fetch_page(
    session: requests.Session,
    *,
    url: str,
    timeout: float,
    robots_text: str,
    user_agent: str,
) -> tuple[requests.Response | None, dict]:
    if not robots_allows(robots_text, user_agent, url):
        return None, {
            "state": "ROBOTS_BLOCKED",
            "requested_url": url,
            "fetched_at_utc": _utc_now(),
        }
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return None, {
            "state": "REQUEST_ERROR",
            "requested_url": url,
            "fetched_at_utc": _utc_now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    fetched_at_utc = _utc_now()
    return response, {
        "requested_url": url,
        **_http_summary(response, fetched_at_utc),
    }


def _is_expected_html(response: requests.Response) -> bool:
    content_type = response.headers.get("Content-Type", "")
    return response.status_code == 200 and "text/html" in content_type.lower()


def _is_provider_host(response: requests.Response) -> bool:
    return (urlparse(response.url).hostname or "").lower() == STOCKANALYSIS_HOST


def _blocked_reason(label: str, evidence: dict) -> str:
    state = evidence.get("state")
    status = evidence.get("status_code")
    if status is not None:
        return f"{label} retrieval unavailable: HTTP {status}"
    return f"{label} retrieval unavailable: {state}"


def _handle_primary_fetch_failure(
    draft_row: dict,
    *,
    target,
    source_url: str,
    response: requests.Response | None,
    evidence: dict,
) -> dict | None:
    if response is None:
        return source_blocked_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=_blocked_reason("forecast", evidence),
        )
    if response.status_code == 404:
        return no_coverage_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason="public StockAnalysis forecast page returned HTTP 404",
        )
    if response.status_code in BLOCKED_HTTP_STATUSES or response.status_code != 200:
        return source_blocked_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=_blocked_reason("forecast", evidence),
        )
    if not _is_provider_host(response):
        return identity_unresolved_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason=f"forecast redirected outside {STOCKANALYSIS_HOST}: {response.url}",
        )
    if not _is_expected_html(response):
        return source_blocked_row(
            draft_row,
            target=target,
            source_url=source_url,
            reason="forecast response was not an expected public HTML page",
        )
    return None


def _validate_config(config: dict, anchor_path: Path) -> None:
    if config.get("schema_version") != 1:
        raise ValueError("weekly acquisition config schema_version must equal 1")
    if config.get("hypothesis_id") != "H021":
        raise ValueError("weekly acquisition config hypothesis_id must equal H021")
    if config.get("source_version") != CANONICAL_SOURCE_VERSION:
        raise ValueError("weekly acquisition config source_version is not canonical")
    if config.get("acquisition_contract_path") != ACQUISITION_CONTRACT_PATH:
        raise ValueError("weekly acquisition config contract path is not canonical")
    if config.get("anchor_path") != str(anchor_path):
        raise ValueError("weekly acquisition config anchor path differs from CLI anchor")
    if config.get("robots_url") != ROBOTS_URL:
        raise ValueError("weekly acquisition must use frozen StockAnalysis robots URL")
    if config.get("outcomes_opened") is not False:
        raise ValueError("weekly acquisition config outcomes_opened must be false")
    if config.get("live_capital_allowed") is not False:
        raise ValueError("weekly acquisition config live_capital_allowed must be false")

    timeout = config.get("timeout_seconds")
    sleep_seconds = config.get("sleep_seconds")
    user_agent = config.get("user_agent")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not isinstance(sleep_seconds, (int, float)) or sleep_seconds < 0:
        raise ValueError("sleep_seconds must be non-negative")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("user_agent must be non-empty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-date", required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--batches", type=Path, required=True)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-draft", type=Path, required=True)
    parser.add_argument("--out-evidence", type=Path, required=True)
    args = parser.parse_args()

    universe = _load_object(args.universe)
    batches = _load_object(args.batches)
    anchor = _load_gzip_object(args.anchor)
    config = _load_object(args.config)
    _validate_config(config, args.anchor)

    draft = build_capture_draft(args.capture_date, universe, batches)
    targets = anchor_targets(anchor)
    draft_symbols = [row["symbol"] for row in draft["observations"]]
    if set(draft_symbols) != set(targets):
        missing = sorted(set(draft_symbols) - set(targets))
        extra = sorted(set(targets) - set(draft_symbols))
        raise ValueError(
            "Sep 11 anchor target set differs from frozen U001 draft; "
            f"missing_targets={missing} extra_targets={extra}"
        )

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

    started_at_utc = _utc_now()
    robots_response = session.get(ROBOTS_URL, timeout=timeout)
    robots_fetched_at_utc = _utc_now()
    if robots_response.status_code != 200:
        raise SystemExit(f"robots.txt returned HTTP {robots_response.status_code}")
    robots_text = robots_response.text
    evidence: dict = {
        "schema_version": 1,
        "hypothesis_id": "H021",
        "capture_date_ist": args.capture_date,
        "started_at_utc": started_at_utc,
        "acquisition_contract_path": ACQUISITION_CONTRACT_PATH,
        "anchor_path": str(args.anchor),
        "universe_path": str(args.universe),
        "batch_spec_path": str(args.batches),
        "robots": {
            "fetched_at_utc": robots_fetched_at_utc,
            "status_code": robots_response.status_code,
            "content_length": len(robots_response.content),
            "sha256": hashlib.sha256(robots_response.content).hexdigest(),
        },
        "rows": [],
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }

    completed_rows: list[dict] = []
    fatal_error: str | None = None
    try:
        for index, draft_row in enumerate(draft["observations"]):
            symbol = draft_row["symbol"]
            target = targets[symbol]
            forecast_source = forecast_url(symbol)
            row_evidence: dict = {
                "symbol": symbol,
                "target_fiscal_period": target.fiscal_period,
                "target_period_ending": target.period_ending,
                "target_eps_currency": target.eps_currency,
                "forecast_source_url": forecast_source,
                "financials_source_url": None,
                "financials_fallback_used": False,
            }

            forecast_response, forecast_evidence = _fetch_page(
                session,
                url=forecast_source,
                timeout=timeout,
                robots_text=robots_text,
                user_agent=user_agent,
            )
            row_evidence["forecast_http"] = forecast_evidence
            failed_row = _handle_primary_fetch_failure(
                draft_row,
                target=target,
                source_url=forecast_source,
                response=forecast_response,
                evidence=forecast_evidence,
            )
            if failed_row is not None:
                completed_rows.append(failed_row)
                row_evidence["capture_state"] = failed_row["data_state"]
                evidence["rows"].append(row_evidence)
                if index + 1 < len(draft["observations"]) and sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                continue

            assert forecast_response is not None
            financials_response: requests.Response | None = None
            financials_source: str | None = None
            currency_on_forecast = forecast_currency_from_html(forecast_response.content)
            if currency_on_forecast is None:
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                financials_source = financials_url(symbol)
                row_evidence["financials_source_url"] = financials_source
                row_evidence["financials_fallback_used"] = True
                financials_response, financials_evidence = _fetch_page(
                    session,
                    url=financials_source,
                    timeout=timeout,
                    robots_text=robots_text,
                    user_agent=user_agent,
                )
                row_evidence["financials_http"] = financials_evidence
                if (
                    financials_response is None
                    or financials_response.status_code != 200
                    or not _is_provider_host(financials_response)
                    or not _is_expected_html(financials_response)
                ):
                    blocked = source_blocked_row(
                        draft_row,
                        target=target,
                        source_url=forecast_response.url,
                        reason=_blocked_reason(
                            "required currency fallback", financials_evidence
                        ),
                    )
                    completed_rows.append(blocked)
                    row_evidence["capture_state"] = blocked["data_state"]
                    evidence["rows"].append(row_evidence)
                    if index + 1 < len(draft["observations"]) and sleep_seconds > 0:
                        time.sleep(sleep_seconds)
                    continue

            try:
                parsed = parse_annual_forecast(
                    symbol=symbol,
                    source_url=forecast_response.url,
                    html=forecast_response.content,
                    expected_fiscal_period=target.fiscal_period,
                    expected_period_ending=target.period_ending,
                    financials_html=(
                        financials_response.content if financials_response is not None else None
                    ),
                    financials_source_url=(
                        financials_response.url if financials_response is not None else None
                    ),
                )
            except (KeyError, TypeError, ValueError) as exc:
                mapped = row_from_parser_error(
                    draft_row,
                    target=target,
                    source_url=forecast_response.url,
                    error=exc,
                )
                completed_rows.append(mapped)
                row_evidence.update(
                    {
                        "parser_pass": False,
                        "parse_error_type": type(exc).__name__,
                        "parse_error": str(exc),
                        "capture_state": mapped["data_state"],
                    }
                )
            else:
                completed = success_row(
                    draft_row,
                    target=target,
                    parsed=parsed,
                    source_url=forecast_response.url,
                )
                completed_rows.append(completed)
                row_evidence.update(
                    {
                        "parser_pass": True,
                        "capture_state": completed["data_state"],
                        "parsed": parsed.to_dict(),
                    }
                )
            evidence["rows"].append(row_evidence)
            if index + 1 < len(draft["observations"]) and sleep_seconds > 0:
                time.sleep(sleep_seconds)
    except StructuralSourceDrift as exc:
        fatal_error = f"{type(exc).__name__}: {exc}"
        evidence["fatal_error"] = fatal_error

    completion = _utc_now()
    evidence["completed_at_utc"] = completion
    evidence["completed_rows"] = len(completed_rows)
    _write_json(args.out_evidence, evidence)
    if fatal_error is not None:
        raise SystemExit(fatal_error)
    if len(completed_rows) != len(draft["observations"]):
        raise SystemExit(
            f"acquisition accounted for {len(completed_rows)} of "
            f"{len(draft['observations'])} frozen symbols"
        )

    snapshot = finalize_capture(draft, completed_rows, completion)
    snapshot["acquisition_contract_path"] = ACQUISITION_CONTRACT_PATH
    errors = validate_full_capture(snapshot, universe, batches)
    if errors:
        evidence["capture_validation_errors"] = errors
        _write_json(args.out_evidence, evidence)
        raise SystemExit(json.dumps({"capture_validation_errors": errors}, indent=2))

    _write_json(args.out_draft, snapshot)
    state_counts: dict[str, int] = {}
    for row in completed_rows:
        state = row["data_state"]
        state_counts[state] = state_counts.get(state, 0) + 1
    print(
        f"captured={len(completed_rows)} states={json.dumps(state_counts, sort_keys=True)} "
        f"draft={args.out_draft} evidence={args.out_evidence}"
    )


if __name__ == "__main__":
    main()
