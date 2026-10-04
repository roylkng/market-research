from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes
from marketlab.marketdata import udiff_url
from marketlab.normalized_valuation import (
    ANNUAL_PERIODS,
    CURRENT_SESSION,
    DIAGNOSTIC_ID,
    NV001SourceError,
    candidate_price_dates,
    parse_annual_basic_eps,
    parse_price_close,
    price_source,
    select_four_year_annual_filings,
    trailing_pe,
)
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot

EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
MIN_CURRENT_PE = 60
MIN_AT_LEAST_3_HISTORY = 60
MIN_ALL_4_HISTORY = 50
MIN_ALL_4_PLUS_CURRENT = 50


def _write_bytes(
    root: Path,
    *,
    kind: str,
    raw: bytes,
    suffix: str,
) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    path = root / kind / "sha256" / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"NV001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".xml", ".html", ".htm", ".zip", ".json"} else ".bin"


def _failure(
    *,
    symbol: str,
    stage: str,
    reason: str,
) -> dict:
    row = {
        "symbol": symbol,
        "stage": stage,
        "reason": reason,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    row["failure_sha256"] = digest(row)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen NV001-D001 own-history P/E source feasibility"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = load_universe_snapshot(args.universe)
    if universe.sha256 != EXPECTED_UNIVERSE_SHA:
        raise AlphaContractError("NV001 D001 universe SHA mismatch")
    if len(universe.members) != 100:
        raise AlphaContractError("NV001 D001 requires frozen 100-member U001")

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    current_day = date.fromisoformat(CURRENT_SESSION)
    current_url = udiff_url(current_day)
    current_raw = client.archive_bytes(current_url)
    current_sha, _ = _write_bytes(
        args.raw_dir,
        kind="price-archives",
        raw=current_raw,
        suffix=".zip",
    )

    price_cache: dict[str, bytes | None] = {current_url: current_raw}
    records: list[dict] = []
    failures: list[dict] = []

    def fetch_price(url: str) -> bytes | None:
        if url in price_cache:
            return price_cache[url]
        try:
            raw = client.archive_bytes(url)
        except NSEAcquisitionError:
            price_cache[url] = None
            return None
        _write_bytes(
            args.raw_dir,
            kind="price-archives",
            raw=raw,
            suffix=".zip",
        )
        price_cache[url] = raw
        return raw

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        print(f"[{index:03d}/100] {symbol}", flush=True)

        try:
            integrated_payload, integrated_raw = (
                client.integrated_financial_filings_with_raw(symbol)
            )
            integrated_sha, _ = _write_bytes(
                args.raw_dir,
                kind="integrated-discovery",
                raw=integrated_raw,
                suffix=".json",
            )
            legacy_payload, legacy_raw = client.financial_results_with_raw(
                symbol,
                period="Quarterly",
            )
            legacy_sha, _ = _write_bytes(
                args.raw_dir,
                kind="legacy-discovery",
                raw=legacy_raw,
                suffix=".json",
            )
        except NSEAcquisitionError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="DISCOVERY_FETCH",
                    reason=str(exc),
                )
            )
            continue

        try:
            basis, candidates = select_four_year_annual_filings(
                integrated_payload,
                legacy_payload,
                symbol=symbol,
            )
        except NV001SourceError as exc:
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="ANNUAL_SELECTION",
                    reason=str(exc),
                )
            )
            continue

        annual_rows = []
        eps_by_period = {}
        fatal = None

        for candidate in candidates:
            try:
                filing_raw = client.archive_bytes(candidate.source_url)
                filing_sha, _ = _write_bytes(
                    args.raw_dir,
                    kind="filings",
                    raw=filing_raw,
                    suffix=_suffix(candidate.source_url),
                )
                eps = parse_annual_basic_eps(
                    filing_raw,
                    candidate=candidate,
                )
                if eps.raw_sha256 != filing_sha:
                    raise NV001SourceError("annual filing raw SHA mismatch")
            except (NSEAcquisitionError, NV001SourceError) as exc:
                fatal = _failure(
                    symbol=symbol,
                    stage=f"ANNUAL_EPS_{candidate.period_end}",
                    reason=str(exc),
                )
                break

            anchor = None
            for day in candidate_price_dates(candidate):
                source_family, source_url = price_source(day)
                raw_price = fetch_price(source_url)
                if raw_price is None:
                    continue
                try:
                    anchor = parse_price_close(
                        raw_price,
                        source_family=source_family,
                        session_date=day,
                        symbol=eps.symbol,
                        expected_isin=eps.isin,
                        source_url=source_url,
                    )
                except NV001SourceError:
                    continue
                break

            if anchor is None:
                fatal = _failure(
                    symbol=symbol,
                    stage=f"PRICE_ANCHOR_{candidate.period_end}",
                    reason="no exact official post-filing price anchor within 10 calendar days",
                )
                break

            pe = trailing_pe(anchor.close_price, eps.basic_eps)
            eps_by_period[candidate.period_end] = eps
            annual_rows.append(
                {
                    "period_end": candidate.period_end,
                    "accounting_basis": basis,
                    "source_family": candidate.source_family,
                    "filing_source_url": candidate.source_url,
                    "filing_discovery_row_sha256": candidate.discovery_row_sha256,
                    "filing_exchange_published_at_utc": (
                        candidate.exchange_published_at_utc
                    ),
                    "filing_raw_sha256": eps.raw_sha256,
                    "filing_symbol": eps.symbol,
                    "filing_isin": eps.isin,
                    "annual_start": eps.annual_start,
                    "annual_basic_eps": eps.basic_eps,
                    "price_session": anchor.session_date,
                    "price_source_family": anchor.source_family,
                    "price_source_url": anchor.source_url,
                    "price_raw_sha256": anchor.raw_sha256,
                    "price_symbol": anchor.symbol,
                    "price_isin": anchor.isin,
                    "close_price": anchor.close_price,
                    "trailing_pe": pe,
                }
            )

        if fatal is not None:
            failures.append(fatal)
            continue

        if len(annual_rows) != len(ANNUAL_PERIODS):
            failures.append(
                _failure(
                    symbol=symbol,
                    stage="ANNUAL_COVERAGE",
                    reason="four annual valuation observations were not materialized",
                )
            )
            continue

        fy26 = eps_by_period["2026-03-31"]
        current_anchor = None
        try:
            current_anchor = parse_price_close(
                current_raw,
                source_family="NSE_UDIFF_BHAVCOPY",
                session_date=current_day,
                symbol=symbol,
                expected_isin=member.isin,
                source_url=current_url,
            )
        except NV001SourceError:
            current_anchor = None

        current_pe = (
            trailing_pe(current_anchor.close_price, fy26.basic_eps)
            if current_anchor is not None
            else None
        )

        record = {
            "schema_version": 1,
            "diagnostic_id": DIAGNOSTIC_ID,
            "symbol": symbol,
            "frozen_isin": member.isin,
            "accounting_basis": basis,
            "integrated_discovery_raw_sha256": integrated_sha,
            "legacy_discovery_raw_sha256": legacy_sha,
            "annual_observations": annual_rows,
            "historical_pe_count": len(annual_rows),
            "current_session": CURRENT_SESSION,
            "current_price_source_url": current_url,
            "current_price_raw_sha256": current_sha,
            "current_close_price": (
                current_anchor.close_price if current_anchor is not None else None
            ),
            "current_trailing_pe": current_pe,
            "return_outcomes_opened": False,
            "model_fitted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        record["record_sha256"] = digest(record)
        records.append(record)

    current_pe_count = sum(
        record["current_trailing_pe"] is not None for record in records
    )
    at_least_3_count = sum(
        record["historical_pe_count"] >= 3 for record in records
    )
    all_4_count = sum(
        record["historical_pe_count"] == 4 for record in records
    )
    all_4_plus_current = sum(
        record["historical_pe_count"] == 4
        and record["current_trailing_pe"] is not None
        for record in records
    )

    failure_stage_counts = Counter(row["stage"] for row in failures)
    failure_reason_counts = Counter(row["reason"] for row in failures)

    threshold_passes = {
        "current_trailing_pe_count": current_pe_count >= MIN_CURRENT_PE,
        "at_least_3_historical_pe_count": at_least_3_count >= MIN_AT_LEAST_3_HISTORY,
        "all_4_historical_pe_count": all_4_count >= MIN_ALL_4_HISTORY,
        "all_4_plus_current_count": all_4_plus_current >= MIN_ALL_4_PLUS_CURRENT,
    }

    panel = {
        "schema_version": 1,
        "diagnostic_id": DIAGNOSTIC_ID,
        "status": "COMPLETE_SOURCE_FEASIBILITY",
        "evidence_class": "HISTORICAL_POINT_IN_TIME_VALUATION_SOURCE_FEASIBILITY_NO_RETURNS",
        "generated_at_utc": generated_at,
        "universe_sha256": universe.sha256,
        "universe_member_count": len(universe.members),
        "annual_periods": list(ANNUAL_PERIODS),
        "current_session": CURRENT_SESSION,
        "record_count": len(records),
        "failure_count": len(failures),
        "current_trailing_pe_count": current_pe_count,
        "at_least_3_historical_pe_count": at_least_3_count,
        "all_4_historical_pe_count": all_4_count,
        "all_4_plus_current_count": all_4_plus_current,
        "failure_stage_counts": dict(sorted(failure_stage_counts.items())),
        "failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "feasibility_thresholds": {
            "minimum_current_trailing_pe": MIN_CURRENT_PE,
            "minimum_at_least_3_historical_pe": MIN_AT_LEAST_3_HISTORY,
            "minimum_all_4_historical_pe": MIN_ALL_4_HISTORY,
            "minimum_all_4_plus_current": MIN_ALL_4_PLUS_CURRENT,
        },
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_normalized_valuation_score_design": all(
            threshold_passes.values()
        ),
        "records": sorted(records, key=lambda row: row["symbol"]),
        "failures": sorted(failures, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "nv001-d001-panel.json").write_text(
        json.dumps(
            panel,
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
        for key, value in panel.items()
        if key not in {"records", "failures"}
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
