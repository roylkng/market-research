from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.fundamental_quality import validate_isin_bridge_payload
from marketlab.marketdata import audit_price_basis_actions, udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.universe import load_universe_snapshot
from marketlab.valuation_history import (
    CURRENT_VALUATION_SESSION,
    SNAPSHOT_QUARTERS,
    VQ001_D001_ID,
    compute_ttm_pe_proxy,
    parse_quarterly_valuation_filing,
    publication_market_date,
    select_snapshot_filings,
    validate_snapshot_issuer_identity,
)

EXPECTED_UNIVERSE_SHA = (
    "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
)
MIN_AT_LEAST_3 = 70
MIN_ALL_4 = 60
MIN_PER_HISTORICAL_SNAPSHOT = 70
MIN_CURRENT = 60
ACTION_FETCH_FROM = "01-10-2025"
ACTION_FETCH_TO = "01-10-2026"


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
        raise RuntimeError(f"VQ001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _suffix(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".xml", ".html", ".htm", ".zip", ".json"} else ".bin"


def _failure(*, symbol: str, snapshot_id: str, stage: str, reason: str) -> dict:
    row = {
        "symbol": symbol.upper(),
        "snapshot_id": snapshot_id,
        "stage": stage,
        "reason": reason,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    row["failure_sha256"] = digest(row)
    return row


def _fetch_archive_cached(
    client: NSEClient,
    cache: dict[str, bytes],
    url: str,
) -> bytes:
    if url not in cache:
        cache[url] = client.archive_bytes(url)
    return cache[url]


def _exact_price_for_isin(
    raw_zip: bytes,
    *,
    session_date: date,
    isin: str,
) -> tuple[str, float]:
    rows = parse_udiff_eq_panel(raw_zip, session_date=session_date)
    matches = [row for row in rows if row.isin == isin]
    if len(matches) != 1:
        raise AlphaContractError(
            f"VQ001 expected one EQ market row for ISIN {isin} on "
            f"{session_date.isoformat()}; found {len(matches)}"
        )
    row = matches[0]
    return row.symbol, row.close_price


def _first_session_after_publication(
    client: NSEClient,
    *,
    market_cache: dict[str, bytes],
    raw_dir: Path,
    published_at_utc: str,
    isin: str,
) -> dict:
    publication_day = date.fromisoformat(publication_market_date(published_at_utc))
    for offset in range(1, 11):
        session = publication_day + timedelta(days=offset)
        url = udiff_url(session)
        try:
            raw = _fetch_archive_cached(client, market_cache, url)
        except NSEAcquisitionError:
            continue

        sha, path = _write_bytes(
            raw_dir,
            kind="market",
            raw=raw,
            suffix=".zip",
        )
        market_symbol, close = _exact_price_for_isin(
            raw,
            session_date=session,
            isin=isin,
        )
        return {
            "session_date": session.isoformat(),
            "market_symbol": market_symbol,
            "isin": isin,
            "close_price": close,
            "source_url": url,
            "raw_sha256": sha,
            "raw_path": path,
        }
    raise AlphaContractError(
        "VQ001 no official NSE market session found within 10 calendar days "
        f"after publication {published_at_utc}"
    )


def _current_session_price(
    client: NSEClient,
    *,
    market_cache: dict[str, bytes],
    raw_dir: Path,
    isin: str,
) -> dict:
    session = date.fromisoformat(CURRENT_VALUATION_SESSION)
    url = udiff_url(session)
    raw = _fetch_archive_cached(client, market_cache, url)
    sha, path = _write_bytes(
        raw_dir,
        kind="market",
        raw=raw,
        suffix=".zip",
    )
    market_symbol, close = _exact_price_for_isin(
        raw,
        session_date=session,
        isin=isin,
    )
    return {
        "session_date": session.isoformat(),
        "market_symbol": market_symbol,
        "isin": isin,
        "close_price": close,
        "source_url": url,
        "raw_sha256": sha,
        "raw_path": path,
    }


def _corporate_action_guard(
    action_payload: object,
    action_raw: bytes,
    *,
    symbol: str,
    period_end: str,
    valuation_session: str,
) -> dict:
    start = date.fromisoformat(period_end) + timedelta(days=1)
    end = date.fromisoformat(valuation_session)
    audit = audit_price_basis_actions(
        action_payload,
        raw_payload=action_raw,
        symbol=symbol,
        start_date=start,
        end_date=end,
    )
    if audit.status != "READY":
        raise AlphaContractError(
            f"VQ001 corporate-action audit unresolved: {list(audit.unresolved_actions)}"
        )
    if audit.relevant_actions:
        raise AlphaContractError(
            f"VQ001 share-changing corporate action blocks snapshot: "
            f"{list(audit.relevant_actions)}"
        )
    return {
        "status": audit.status,
        "version": audit.version,
        "raw_sha256": audit.raw_sha256,
        "relevant_actions": [],
    }


def _parse_selected_filings(
    *,
    client: NSEClient,
    selected: dict,
    filing_cache: dict[str, bytes],
    raw_dir: Path,
) -> dict:
    parsed = {}
    for period_end, selected_row in selected.items():
        candidate = selected_row.candidate
        raw = _fetch_archive_cached(client, filing_cache, candidate.source_url)
        sha, raw_path = _write_bytes(
            raw_dir,
            kind="filings",
            raw=raw,
            suffix=_suffix(candidate.source_url),
        )
        facts = parse_quarterly_valuation_filing(raw, candidate=candidate)
        if facts.raw_sha256 != sha:
            raise AlphaContractError("VQ001 filing raw SHA mismatch")
        parsed[period_end] = {
            "facts": facts,
            "source_family": selected_row.source_family,
            "raw_path": raw_path,
        }
    return parsed


def _build_snapshot(
    *,
    member,
    snapshot_id: str,
    required_periods: tuple[str, ...],
    integrated_payload: object,
    legacy_payload: object,
    bridge_index: dict[str, dict[str, str]],
    client: NSEClient,
    filing_cache: dict[str, bytes],
    market_cache: dict[str, bytes],
    raw_dir: Path,
    action_payload: object,
    action_raw: bytes,
    current: bool,
) -> dict:
    basis, selected = select_snapshot_filings(
        integrated_payload,
        legacy_payload,
        symbol=member.symbol,
        required_periods=required_periods,
    )
    parsed = _parse_selected_filings(
        client=client,
        selected=selected,
        filing_cache=filing_cache,
        raw_dir=raw_dir,
    )
    target_period = required_periods[-1]
    target = parsed[target_period]["facts"]
    components = [parsed[period]["facts"] for period in required_periods]

    target_time = datetime.fromisoformat(target.published_at_utc).astimezone(UTC)
    for component in components:
        component_time = datetime.fromisoformat(component.published_at_utc).astimezone(UTC)
        if component_time > target_time:
            raise AlphaContractError(
                "VQ001 component filing was published after latest-quarter filing"
            )

    identity_state = validate_snapshot_issuer_identity(
        frozen_symbol=member.symbol,
        frozen_isin=member.isin,
        target=target,
        components=components,
        bridge_index=bridge_index,
        as_of_date="2026-10-04",
    )

    if target.share_count is None:
        raise AlphaContractError("VQ001 latest filing share count is unavailable")
    if not target.isin:
        raise AlphaContractError("VQ001 latest filing ISIN is unavailable")

    quarterly_profits = []
    for component in components:
        if component.total_profit_inr is None:
            raise AlphaContractError("VQ001 quarterly PAT is unavailable")
        quarterly_profits.append(float(component.total_profit_inr))

    if current:
        price = _current_session_price(
            client,
            market_cache=market_cache,
            raw_dir=raw_dir,
            isin=target.isin,
        )
    else:
        price = _first_session_after_publication(
            client,
            market_cache=market_cache,
            raw_dir=raw_dir,
            published_at_utc=target.published_at_utc,
            isin=target.isin,
        )

    action_audit = _corporate_action_guard(
        action_payload,
        action_raw,
        symbol=member.symbol,
        period_end=target_period,
        valuation_session=price["session_date"],
    )

    valuation = compute_ttm_pe_proxy(
        quarterly_profits_inr=quarterly_profits,
        share_count=float(target.share_count),
        price_inr=float(price["close_price"]),
    )

    filing_rows = []
    for period_end in required_periods:
        row = parsed[period_end]
        facts = row["facts"]
        filing_rows.append(
            {
                "period_end": period_end,
                "accounting_basis": facts.accounting_basis,
                "reported_symbol": facts.symbol,
                "isin": facts.isin,
                "published_at_utc": facts.published_at_utc,
                "source_family": row["source_family"],
                "source_url": facts.source_url,
                "raw_sha256": facts.raw_sha256,
                "total_profit_inr": facts.total_profit_inr,
            }
        )

    return {
        "snapshot_id": snapshot_id,
        "latest_quarter_end": target_period,
        "required_quarters": list(required_periods),
        "accounting_basis": basis,
        "issuer_identity_state": identity_state,
        "latest_filing_symbol": target.symbol,
        "latest_filing_isin": target.isin,
        "latest_filing_published_at_utc": target.published_at_utc,
        "latest_paid_up_equity_share_capital_inr": (
            target.paid_up_equity_share_capital_inr
        ),
        "latest_face_value_per_share_inr": target.face_value_per_share_inr,
        "latest_share_count": target.share_count,
        "valuation_session": price["session_date"],
        "market_symbol": price["market_symbol"],
        "market_isin": price["isin"],
        "market_close_price_inr": price["close_price"],
        "market_source_url": price["source_url"],
        "market_raw_sha256": price["raw_sha256"],
        "corporate_action_audit": action_audit,
        "quarterly_filings": filing_rows,
        **valuation,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen VQ001-D001 point-in-time valuation source feasibility"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--isin-bridges", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = load_universe_snapshot(args.universe)
    if universe.sha256 != EXPECTED_UNIVERSE_SHA:
        raise AlphaContractError("VQ001 D001 universe SHA mismatch")
    if len(universe.members) != 100:
        raise AlphaContractError("VQ001 D001 requires frozen 100-member U001")

    bridge_raw = args.isin_bridges.read_bytes()
    bridge_payload = json.loads(bridge_raw.decode("utf-8"))
    bridge_index = validate_isin_bridge_payload(bridge_payload)
    bridge_sha = sha256_bytes(bridge_raw)

    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    filing_cache: dict[str, bytes] = {}
    market_cache: dict[str, bytes] = {}
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    records = []
    all_failures = []

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        print(f"[{index:03d}/100] {symbol}", flush=True)

        integrated_payload: object = []
        legacy_payload: object = []
        discovery = {}
        try:
            integrated_payload, integrated_raw = (
                client.integrated_financial_filings_with_raw(symbol)
            )
            sha, path = _write_bytes(
                args.raw_dir,
                kind="discovery-integrated",
                raw=integrated_raw,
                suffix=".json",
            )
            discovery["integrated"] = {"raw_sha256": sha, "raw_path": path}
        except NSEAcquisitionError as exc:
            discovery["integrated_error"] = str(exc)

        try:
            legacy_payload, legacy_raw = client.financial_results_with_raw(symbol)
            sha, path = _write_bytes(
                args.raw_dir,
                kind="discovery-legacy",
                raw=legacy_raw,
                suffix=".json",
            )
            discovery["legacy"] = {"raw_sha256": sha, "raw_path": path}
        except NSEAcquisitionError as exc:
            discovery["legacy_error"] = str(exc)

        try:
            action_payload, action_raw = client.corporate_actions_with_raw(
                symbol,
                from_date=ACTION_FETCH_FROM,
                to_date=ACTION_FETCH_TO,
            )
            action_sha, action_path = _write_bytes(
                args.raw_dir,
                kind="corporate-actions",
                raw=action_raw,
                suffix=".json",
            )
            action_source = {
                "raw_sha256": action_sha,
                "raw_path": action_path,
                "from_date": ACTION_FETCH_FROM,
                "to_date": ACTION_FETCH_TO,
            }
            action_error = None
        except NSEAcquisitionError as exc:
            action_payload = []
            action_raw = b""
            action_source = None
            action_error = str(exc)

        snapshot_results = {}
        snapshot_failures = []

        for latest_period, required_periods in SNAPSHOT_QUARTERS.items():
            snapshot_id = f"HISTORICAL_{latest_period}"
            if action_error is not None:
                snapshot_failures.append(
                    _failure(
                        symbol=symbol,
                        snapshot_id=snapshot_id,
                        stage="CORPORATE_ACTION_FETCH",
                        reason=action_error,
                    )
                )
                continue
            try:
                snapshot_results[snapshot_id] = _build_snapshot(
                    member=member,
                    snapshot_id=snapshot_id,
                    required_periods=required_periods,
                    integrated_payload=integrated_payload,
                    legacy_payload=legacy_payload,
                    bridge_index=bridge_index,
                    client=client,
                    filing_cache=filing_cache,
                    market_cache=market_cache,
                    raw_dir=args.raw_dir,
                    action_payload=action_payload,
                    action_raw=action_raw,
                    current=False,
                )
            except (AlphaContractError, NSEAcquisitionError) as exc:
                snapshot_failures.append(
                    _failure(
                        symbol=symbol,
                        snapshot_id=snapshot_id,
                        stage="SNAPSHOT_BUILD",
                        reason=str(exc),
                    )
                )

        current_id = f"CURRENT_{CURRENT_VALUATION_SESSION}"
        current_periods = SNAPSHOT_QUARTERS["2026-06-30"]
        if action_error is not None:
            snapshot_failures.append(
                _failure(
                    symbol=symbol,
                    snapshot_id=current_id,
                    stage="CORPORATE_ACTION_FETCH",
                    reason=action_error,
                )
            )
        else:
            try:
                snapshot_results[current_id] = _build_snapshot(
                    member=member,
                    snapshot_id=current_id,
                    required_periods=current_periods,
                    integrated_payload=integrated_payload,
                    legacy_payload=legacy_payload,
                    bridge_index=bridge_index,
                    client=client,
                    filing_cache=filing_cache,
                    market_cache=market_cache,
                    raw_dir=args.raw_dir,
                    action_payload=action_payload,
                    action_raw=action_raw,
                    current=True,
                )
            except (AlphaContractError, NSEAcquisitionError) as exc:
                snapshot_failures.append(
                    _failure(
                        symbol=symbol,
                        snapshot_id=current_id,
                        stage="CURRENT_SNAPSHOT_BUILD",
                        reason=str(exc),
                    )
                )

        historical_valid = sum(
            int(f"HISTORICAL_{period}" in snapshot_results)
            for period in SNAPSHOT_QUARTERS
        )
        current_valid = current_id in snapshot_results
        record = {
            "schema_version": 1,
            "diagnostic_id": VQ001_D001_ID,
            "symbol": symbol,
            "frozen_isin": member.isin,
            "discovery": discovery,
            "corporate_action_source": action_source,
            "historical_valid_snapshot_count": historical_valid,
            "all_four_historical_valid": historical_valid == 4,
            "current_snapshot_valid": current_valid,
            "snapshots": snapshot_results,
            "snapshot_failures": snapshot_failures,
            "return_outcomes_opened": False,
            "model_fitted": False,
            "portfolio_eligibility_allowed": False,
            "live_capital_allowed": False,
        }
        record["record_sha256"] = digest(record)
        records.append(record)
        all_failures.extend(snapshot_failures)

    historical_counts = {
        period: sum(
            int(f"HISTORICAL_{period}" in record["snapshots"])
            for record in records
        )
        for period in SNAPSHOT_QUARTERS
    }
    at_least_3 = sum(
        record["historical_valid_snapshot_count"] >= 3
        for record in records
    )
    all_4 = sum(record["all_four_historical_valid"] for record in records)
    current_count = sum(record["current_snapshot_valid"] for record in records)

    threshold_passes = {
        "at_least_70_companies_with_3_historical": at_least_3 >= MIN_AT_LEAST_3,
        "at_least_60_companies_with_all_4_historical": all_4 >= MIN_ALL_4,
        "each_historical_snapshot_at_least_70": all(
            count >= MIN_PER_HISTORICAL_SNAPSHOT
            for count in historical_counts.values()
        ),
        "current_snapshot_at_least_60": current_count >= MIN_CURRENT,
    }

    stage_counts = Counter(row["stage"] for row in all_failures)
    reason_counts = Counter(row["reason"] for row in all_failures)
    panel = {
        "schema_version": 1,
        "diagnostic_id": VQ001_D001_ID,
        "status": "COMPLETE_SOURCE_FEASIBILITY",
        "evidence_class": "HISTORICAL_POINT_IN_TIME_VALUATION_SOURCE_FEASIBILITY_NO_RETURNS",
        "generated_at_utc": generated_at,
        "universe_sha256": universe.sha256,
        "universe_member_count": len(universe.members),
        "isin_bridge_sha256": bridge_sha,
        "historical_snapshot_grid": {
            key: list(value) for key, value in SNAPSHOT_QUARTERS.items()
        },
        "current_valuation_session": CURRENT_VALUATION_SESSION,
        "historical_snapshot_valid_counts": historical_counts,
        "companies_with_at_least_3_historical": at_least_3,
        "companies_with_all_4_historical": all_4,
        "current_snapshot_valid_count": current_count,
        "feasibility_thresholds": {
            "minimum_companies_with_3_historical": MIN_AT_LEAST_3,
            "minimum_companies_with_all_4_historical": MIN_ALL_4,
            "minimum_each_historical_snapshot": MIN_PER_HISTORICAL_SNAPSHOT,
            "minimum_current_snapshot": MIN_CURRENT,
        },
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_normalized_valuation_design": all(
            threshold_passes.values()
        ),
        "failure_stage_counts": dict(sorted(stage_counts.items())),
        "failure_reason_counts": dict(sorted(reason_counts.items())),
        "records": sorted(records, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "vq001-d001-panel.json").write_text(
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
        if key not in {"records", "failure_reason_counts"}
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
