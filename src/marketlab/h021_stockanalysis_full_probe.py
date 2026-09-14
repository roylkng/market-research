from __future__ import annotations

from collections import Counter


def _require_object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object")
    return value


def validate_full_probe_config(config: dict) -> list[str]:
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if config.get("hypothesis_id") != "H021-STOCKANALYSIS-FULL-U001-PROBE":
        errors.append("unexpected hypothesis_id")
    if config.get("expected_total_symbols") != 100:
        errors.append("expected_total_symbols must equal frozen U001 size 100")
    if config.get("batch_ids") != ["B01", "B02"]:
        errors.append("batch_ids must equal frozen H021 batches B01/B02")
    if config.get("retain_raw_provider_html") is not False:
        errors.append("retain_raw_provider_html must be false")
    if config.get("outcomes_opened") is not False:
        errors.append("outcomes_opened must be false")
    if config.get("live_capital_allowed") is not False:
        errors.append("live_capital_allowed must be false")
    timeout = config.get("timeout_seconds")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        errors.append("timeout_seconds must be positive")
    sleep = config.get("sleep_seconds_between_requests")
    if not isinstance(sleep, (int, float)) or isinstance(sleep, bool) or sleep < 3:
        errors.append("sleep_seconds_between_requests must be at least 3 seconds")
    return errors


def build_batch_targets(
    anchor: dict,
    universe: dict,
    batch_spec: dict,
    batch_id: str,
) -> list[dict]:
    anchor_rows = anchor.get("observations")
    universe_members = universe.get("members")
    batches = batch_spec.get("batches")
    if not isinstance(anchor_rows, list) or not isinstance(universe_members, list):
        raise ValueError("anchor observations and universe members must be lists")
    if not isinstance(batches, list):
        raise ValueError("batch spec batches must be a list")

    matching_batches = [row for row in batches if row.get("batch_id") == batch_id]
    if len(matching_batches) != 1:
        raise ValueError(f"batch {batch_id} must exist exactly once")
    batch = matching_batches[0]
    rank_min = batch.get("rank_min")
    rank_max = batch.get("rank_max")
    if not isinstance(rank_min, int) or not isinstance(rank_max, int):
        raise ValueError(f"batch {batch_id} rank bounds must be integers")

    anchor_by_symbol = {
        row.get("symbol"): row
        for row in anchor_rows
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    }
    universe_by_symbol = {
        row.get("symbol"): row
        for row in universe_members
        if isinstance(row, dict) and isinstance(row.get("symbol"), str)
    }
    if set(anchor_by_symbol) != set(universe_by_symbol):
        missing = sorted(set(universe_by_symbol) - set(anchor_by_symbol))
        extra = sorted(set(anchor_by_symbol) - set(universe_by_symbol))
        raise ValueError(f"anchor/universe symbol mismatch missing={missing} extra={extra}")

    selected_members = sorted(
        (
            member
            for member in universe_members
            if isinstance(member, dict)
            and isinstance(member.get("rank"), int)
            and rank_min <= member["rank"] <= rank_max
        ),
        key=lambda row: row["rank"],
    )
    expected_count = rank_max - rank_min + 1
    if len(selected_members) != expected_count:
        raise ValueError(
            f"batch {batch_id} resolved {len(selected_members)} members; expected {expected_count}"
        )

    targets: list[dict] = []
    for member in selected_members:
        symbol = member["symbol"]
        anchor_row = anchor_by_symbol[symbol]
        fiscal_period = anchor_row.get("fiscal_period")
        period_ending = anchor_row.get("period_ending")
        eps_currency = anchor_row.get("eps_currency")
        if not isinstance(fiscal_period, str) or not fiscal_period:
            raise ValueError(f"anchor fiscal_period missing for {symbol}")
        if not isinstance(period_ending, str) or not period_ending:
            raise ValueError(f"anchor period_ending missing for {symbol}")
        if not isinstance(eps_currency, str) or not eps_currency:
            raise ValueError(f"anchor eps_currency missing for {symbol}")
        targets.append(
            {
                "symbol": symbol,
                "rank": member["rank"],
                "isin": member.get("isin"),
                "batch_id": batch_id,
                "anchor_fiscal_period": fiscal_period,
                "anchor_period_ending": period_ending,
                "anchor_eps_currency": eps_currency,
                "anchor_consensus_eps": anchor_row.get("consensus_eps"),
            }
        )
    return targets


def summarize_probe_rows(rows: list[dict]) -> dict:
    states = Counter(str(row.get("state")) for row in rows)
    currency_sources = Counter(
        str(row.get("parsed", {}).get("eps_currency_source_url"))
        for row in rows
        if isinstance(row.get("parsed"), dict)
    )
    return {
        "total": len(rows),
        "probe_pass": sum(bool(row.get("probe_pass")) for row in rows),
        "parser_pass": sum(bool(row.get("parser_pass")) for row in rows),
        "semantic_match_pass": sum(bool(row.get("semantic_match_pass")) for row in rows),
        "state_counts": dict(sorted(states.items())),
        "currency_source_counts": dict(sorted(currency_sources.items())),
    }


def aggregate_shard_reports(config: dict, reports: list[dict]) -> dict:
    config_errors = validate_full_probe_config(config)
    if config_errors:
        raise ValueError({"config_errors": config_errors})

    expected_batches = list(config["batch_ids"])
    by_batch: dict[str, dict] = {}
    all_rows: list[dict] = []
    for raw in reports:
        report = _require_object(raw, "shard report")
        if report.get("hypothesis_id") != "H021-STOCKANALYSIS-FULL-U001-PROBE":
            raise ValueError("unexpected shard hypothesis_id")
        if report.get("outcomes_opened") is not False:
            raise ValueError("shard outcomes_opened must be false")
        if report.get("live_capital_allowed") is not False:
            raise ValueError("shard live_capital_allowed must be false")
        batch_id = report.get("batch_id")
        if batch_id not in expected_batches:
            raise ValueError(f"unexpected shard batch_id: {batch_id}")
        if batch_id in by_batch:
            raise ValueError(f"duplicate shard report for {batch_id}")
        rows = report.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"shard {batch_id} rows must be a list")
        by_batch[batch_id] = report
        all_rows.extend(rows)

    if sorted(by_batch) != sorted(expected_batches):
        raise ValueError(
            f"missing shard reports; expected={sorted(expected_batches)} got={sorted(by_batch)}"
        )

    symbols = [row.get("symbol") for row in all_rows if isinstance(row, dict)]
    if len(symbols) != config["expected_total_symbols"]:
        raise ValueError(
            f"aggregate row count {len(symbols)} != expected {config['expected_total_symbols']}"
        )
    if len(set(symbols)) != len(symbols):
        raise ValueError("aggregate contains duplicate symbols")

    rows_sorted = sorted(all_rows, key=lambda row: int(row["rank"]))
    summary = summarize_probe_rows(rows_sorted)
    return {
        "schema_version": 1,
        "hypothesis_id": "H021-STOCKANALYSIS-FULL-U001-PROBE",
        "batch_ids": expected_batches,
        "summary": summary,
        "rows": rows_sorted,
        "decision": {
            "full_u001_probe_complete": summary["total"] == config["expected_total_symbols"],
            "full_u001_parser_pass_all": summary["parser_pass"] == config["expected_total_symbols"],
            "full_u001_semantic_match_all": (
                summary["semantic_match_pass"] == config["expected_total_symbols"]
            ),
            "full_u001_probe_pass_all": summary["probe_pass"] == config["expected_total_symbols"],
        },
        "outcomes_opened": False,
        "live_capital_allowed": False,
    }
