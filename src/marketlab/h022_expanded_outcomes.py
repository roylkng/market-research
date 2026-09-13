from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from marketlab.h022_expanded_features import validate_expanded_feature_panel
from marketlab.h022_outcomes import (
    HORIZONS,
    MARKET_DATA_CUTOFF,
    PRIMARY_HORIZON,
    ROUND_TRIP_COST_PP,
    HistoricalSession,
    blocked_actions,
    classify_primary,
    evaluate_horizon,
    first_entry_session,
    horizon_session,
)

HYPOTHESIS_ID = "H022"
EXECUTION_RULE_ID = "H022-X001"
FEATURE_PANEL_SHA256 = "f07dd7b9c7925b53b10bca1926b40a086832df3bbe6dbdb42caea43164d617fa"
CHALLENGE_SIGNAL_COUNT = 753
EVIDENCE_CLASS = "HISTORICAL_POINT_IN_TIME_NIFTY200_CHALLENGER"


class ExpandedOutcomeError(ValueError):
    """Raised when expanded H022 historical outcomes cannot be reconstructed safely."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ExpandedOutcomeError(
            "expanded H022 outcome payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _gross_return_pct(entry: float, exit_value: float) -> float:
    result = (exit_value / entry - 1.0) * 100.0
    if not math.isfinite(result):
        raise ExpandedOutcomeError("computed return is non-finite")
    return result


def challenge_rows(feature_panel: dict[str, Any]) -> list[dict[str, Any]]:
    validate_expanded_feature_panel(feature_panel)
    if feature_panel.get("panel_sha256") != FEATURE_PANEL_SHA256:
        raise ExpandedOutcomeError("expanded H022 feature panel digest changed")
    rows = [
        row
        for row in feature_panel["records"]
        if row.get("feature_status") == "SIGNAL"
        and row.get("evaluation_eligible") is True
    ]
    if len(rows) != CHALLENGE_SIGNAL_COUNT:
        raise ExpandedOutcomeError(
            f"expected {CHALLENGE_SIGNAL_COUNT} expanded challenge signals, found {len(rows)}"
        )
    return rows


def build_expanded_outcome_report(
    feature_panel: dict[str, Any],
    *,
    sessions: tuple[HistoricalSession, ...],
    stock_bars: dict[tuple[str, str], dict[str, Any] | None],
    benchmark_bars: dict[str, dict[str, Any]],
    corporate_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    challenge = challenge_rows(feature_panel)
    session_index = {row.session_date: index for index, row in enumerate(sessions)}
    records: list[dict[str, Any]] = []

    for feature in challenge:
        symbol = str(feature["symbol"])
        entry_result = first_entry_session(
            str(feature["exchange_published_at_utc"]), sessions
        )
        row: dict[str, Any] = {
            "source_id": feature["source_id"],
            "symbol": symbol,
            "exchange_published_at_utc": feature["exchange_published_at_utc"],
            "primary_signal": feature["primary_signal"],
            "membership_status": feature["membership_status"],
            "entry_session": None,
            "entry_stock_bar": None,
            "entry_benchmark_bar": None,
            "horizons": {},
        }
        if entry_result is None:
            for horizon in HORIZONS:
                row["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
            records.append(row)
            continue

        entry_index, entry_session = entry_result
        row["entry_session"] = entry_session.to_dict()
        entry_stock = stock_bars.get((entry_session.session_date, symbol))
        entry_benchmark = benchmark_bars.get(entry_session.session_date)
        row["entry_stock_bar"] = entry_stock
        row["entry_benchmark_bar"] = entry_benchmark
        action_audit = corporate_actions.get(symbol)

        for horizon in HORIZONS:
            exit_session = horizon_session(
                sessions, entry_index=entry_index, horizon=horizon
            )
            if exit_session is None:
                row["horizons"][str(horizon)] = {"status": "NOT_MATURE"}
                continue
            if exit_session.session_date not in session_index:
                raise ExpandedOutcomeError(
                    "horizon exit session is not in frozen calendar"
                )
            if entry_stock is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if entry_benchmark is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_ENTRY_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if action_audit is None or action_audit.get("status") != "READY":
                row["horizons"][str(horizon)] = {
                    "status": "CORPORATE_ACTION_AUDIT_UNRESOLVED",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            actions = blocked_actions(
                action_audit,
                entry_date=entry_session.session_date,
                exit_date=exit_session.session_date,
            )
            if actions:
                row["horizons"][str(horizon)] = {
                    "status": "CORPORATE_ACTION_BLOCKED",
                    "exit_session": exit_session.to_dict(),
                    "blocked_actions": list(actions),
                }
                continue

            exit_stock = stock_bars.get((exit_session.session_date, symbol))
            exit_benchmark = benchmark_bars.get(exit_session.session_date)
            if exit_stock is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_STOCK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue
            if exit_benchmark is None:
                row["horizons"][str(horizon)] = {
                    "status": "MISSING_EXIT_BENCHMARK_BAR",
                    "exit_session": exit_session.to_dict(),
                }
                continue

            stock_return = _gross_return_pct(
                float(entry_stock["open"]), float(exit_stock["close"])
            )
            benchmark_return = _gross_return_pct(
                float(entry_benchmark["open"]), float(exit_benchmark["close"])
            )
            excess = stock_return - benchmark_return
            row["horizons"][str(horizon)] = {
                "status": "COMPLETE",
                "exit_session": exit_session.to_dict(),
                "exit_stock_bar": exit_stock,
                "exit_benchmark_bar": exit_benchmark,
                "stock_return_pct": stock_return,
                "benchmark_return_pct": benchmark_return,
                "gross_excess_pp": excess,
                "cost_adjusted_excess_pp": excess - ROUND_TRIP_COST_PP,
                "beat_benchmark": excess > 0,
            }
        records.append(row)

    report: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "feature_panel_sha256": FEATURE_PANEL_SHA256,
        "evidence_class": EVIDENCE_CLASS,
        "market_data_cutoff_session": MARKET_DATA_CUTOFF.isoformat(),
        "challenge_signal_count": len(records),
        "records": records,
    }
    report["report_sha256"] = _canonical_hash(report)
    return report


def summarize_expanded_outcomes(report: dict[str, Any]) -> dict[str, Any]:
    stored = report.get("report_sha256")
    unsigned = dict(report)
    unsigned.pop("report_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise ExpandedOutcomeError("expanded H022 outcome report hash mismatch")
    if report.get("feature_panel_sha256") != FEATURE_PANEL_SHA256:
        raise ExpandedOutcomeError("expanded H022 outcome feature panel changed")
    if report.get("challenge_signal_count") != CHALLENGE_SIGNAL_COUNT:
        raise ExpandedOutcomeError("expanded H022 challenge count changed")
    horizons = {
        str(horizon): evaluate_horizon(report, horizon=horizon) for horizon in HORIZONS
    }
    classification = classify_primary(horizons[str(PRIMARY_HORIZON)])
    summary: dict[str, Any] = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "execution_rule_id": EXECUTION_RULE_ID,
        "feature_panel_sha256": FEATURE_PANEL_SHA256,
        "outcome_report_sha256": stored,
        "evidence_class": EVIDENCE_CLASS,
        "market_data_cutoff_session": report["market_data_cutoff_session"],
        "challenge_signal_count": CHALLENGE_SIGNAL_COUNT,
        "primary_horizon_sessions": PRIMARY_HORIZON,
        "primary_classification": classification,
        "horizons": horizons,
        "live_capital_allowed": False,
    }
    summary["summary_sha256"] = _canonical_hash(summary)
    return summary
