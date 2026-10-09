"""Outcome-blind H021 analyst-panel composition diagnostic.

This deliberately does not modify H021's frozen EPS revision, top-decile
selection, DR001 gate, or portfolio eligibility. A changed analyst count is an
audit question, not proof of biased or invalid consensus EPS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from math import isfinite
from pathlib import Path
from typing import Any

AUDIT_ID = "H021-P002-ANALYST-COMPOSITION-DESCRIPTIVE-v1"
PRIMARY_SIGNAL = "28-35 day same-period consensus EPS revision"


def _analyst_count(value: object, symbol: str, period: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"{symbol} {period}: invalid analyst count")
    return value


def _valid_revision(value: object) -> bool:
    return (
        type(value) in (float, int)
        and isfinite(float(value))
    )


def build_analyst_composition_audit(comparison: dict[str, Any]) -> dict[str, Any]:
    """Describe analyst coverage churn without changing H021 eligibility."""
    if comparison.get("schema_version") != 1 or comparison.get("hypothesis_id") != "H021":
        raise ValueError("H021 comparison schema/identity mismatch")
    if comparison.get("primary_signal") != PRIMARY_SIGNAL:
        raise ValueError("H021 frozen primary signal mismatch")
    if comparison.get("outcomes_opened") is not False:
        raise ValueError("return outcomes must remain unopened")
    if comparison.get("live_capital_allowed") is not False:
        raise ValueError("live capital must remain disabled")

    observations = comparison.get("revision_observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("nonempty revision_observations required")
    top_symbols = comparison.get("primary_top_decile_symbols")
    if not isinstance(top_symbols, list) or not all(
        isinstance(item, str) and item for item in top_symbols
    ) or len(top_symbols) != len(set(top_symbols)):
        raise ValueError("invalid primary_top_decile_symbols")
    if comparison.get("primary_top_decile_count") != len(top_symbols):
        raise ValueError("primary top-decile count mismatch")

    top_set = set(top_symbols)
    output_rows: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    eligible_count = 0
    for observation in observations:
        if not isinstance(observation, dict):
            raise TypeError("revision observation must be an object")
        symbol = observation.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in seen_symbols:
            raise ValueError("missing or duplicate H021 symbol")
        seen_symbols.add(symbol)
        available = observation.get("primary_signal_available")
        reason = observation.get("primary_signal_reason")
        if type(available) is not bool or not isinstance(reason, str) or not reason:
            raise ValueError(f"{symbol}: invalid primary signal availability/reason")
        revision = observation.get("eps_revision_pct")
        if available:
            if reason != "ELIGIBLE" or not _valid_revision(revision):
                raise ValueError(f"{symbol}: eligible primary signal is invalid")
            eligible_count += 1
        elif reason == "ELIGIBLE" or revision is not None:
            raise ValueError(f"{symbol}: ineligible primary signal cannot have revision")
        if symbol in top_set and not available:
            raise ValueError(f"{symbol}: top-decile symbol is ineligible")

        prior = _analyst_count(observation.get("analyst_count_prior"), symbol, "prior")
        current = _analyst_count(observation.get("analyst_count_current"), symbol, "current")
        if available and (prior is None or prior < 5 or current is None or current < 5):
            raise ValueError(f"{symbol}: primary eligible row violates coverage >=5")

        delta = (current - prior) if prior is not None and current is not None else None
        change_ratio = (delta / prior) if delta is not None and prior > 0 else None
        direction = (
            "UNAVAILABLE" if delta is None
            else "DECREASED" if delta < 0
            else "INCREASED" if delta > 0
            else "UNCHANGED"
        )
        output_rows.append({
            "symbol": symbol,
            "primary_signal_available": available,
            "primary_signal_reason": reason,
            "primary_top_decile": symbol in top_set,
            "eps_revision_pct": revision,
            "analyst_count_prior": prior,
            "analyst_count_current": current,
            "analyst_count_delta": delta,
            "analyst_count_change_ratio": change_ratio,
            "analyst_count_direction": direction,
        })
    if not top_set.issubset(seen_symbols):
        raise ValueError("top decile references missing H021 symbol")
    if comparison.get("primary_signal_available_count") != eligible_count:
        raise ValueError("primary signal available count mismatch")

    output_rows.sort(key=lambda item: item["symbol"])
    eligible_rows = [row for row in output_rows if row["primary_signal_available"]]
    selected_rows = [row for row in eligible_rows if row["primary_top_decile"]]

    def descriptive_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        directions = Counter(row["analyst_count_direction"] for row in rows)
        return {
            "count": len(rows),
            "decreased": directions["DECREASED"],
            "unchanged": directions["UNCHANGED"],
            "increased": directions["INCREASED"],
            "unavailable": directions["UNAVAILABLE"],
            "decline_at_least_30pct": sum(
                row["analyst_count_change_ratio"] is not None
                and row["analyst_count_change_ratio"] <= -0.30
                for row in rows
            ),
            "decline_at_least_50pct": sum(
                row["analyst_count_change_ratio"] is not None
                and row["analyst_count_change_ratio"] <= -0.50
                for row in rows
            ),
        }

    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "POST_SIGNAL_OUTCOME_BLIND_COVERAGE_DIAGNOSTIC_NOT_ALPHA",
        "prior_capture_date_ist": comparison.get("prior_capture_date_ist"),
        "current_capture_date_ist": comparison.get("current_capture_date_ist"),
        "primary_signal": PRIMARY_SIGNAL,
        "total_symbol_count": len(output_rows),
        "primary_signal_available_count": eligible_count,
        "primary_top_decile_symbols_unchanged": top_symbols,
        "eligible_panel": descriptive_counts(eligible_rows),
        "primary_top_decile_panel": descriptive_counts(selected_rows),
        "observations": output_rows,
        "coverage_churn_changes_primary_rank_or_selection": False,
        "contains_return_or_price_outcomes": False,
        "promotes_research_or_portfolio_gate": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    original_bytes = args.comparison.read_bytes()
    result = build_analyst_composition_audit(json.loads(original_bytes))
    result["comparison_raw_sha256"] = hashlib.sha256(original_bytes).hexdigest()
    output = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
