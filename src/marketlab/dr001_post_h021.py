from __future__ import annotations

from collections import Counter
from typing import Any

PACK_ID = "DR001-POST-H021-EVIDENCE-v1"
EXPECTED_SYMBOLS = {
    "COFORGE",
    "AUROPHARMA",
    "MOTHERSON",
    "HINDALCO",
    "PERSISTENT",
}


def _dependency_state(value: float) -> str:
    if value >= 40.0:
        return "FORWARD_EARNINGS_DEPENDENCY_HIGH"
    if value >= 20.0:
        return "FORWARD_EARNINGS_DEPENDENCY_MODERATE"
    return "FORWARD_EARNINGS_DEPENDENCY_LOW"


def _revision_sign(value: object, available: object) -> str:
    if available is not True or not isinstance(value, (int, float)) or isinstance(value, bool):
        return "UNAVAILABLE"
    revision = float(value)
    if revision > 0:
        return "POSITIVE"
    if revision < 0:
        return "NEGATIVE"
    return "FLAT"


def _index(rows: object, *, field: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise TypeError(f"{label} must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{label} rows must be objects")
        symbol = row.get(field)
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"{label} row requires {field}")
        if symbol in result:
            raise ValueError(f"{label} duplicate symbol: {symbol}")
        result[symbol] = row
    return result


def build_post_h021_evidence_pack(
    pre_evidence: dict[str, Any],
    comparison: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    if pre_evidence.get("pack_id") != "DR001-PRE-H021-EVIDENCE-2026-10-04-v1":
        raise ValueError("unexpected DR001 pre-H021 evidence pack")
    if pre_evidence.get("return_outcomes_opened") is not False:
        raise ValueError("pre-H021 evidence must keep returns closed")
    if pre_evidence.get("portfolio_eligibility_allowed") is not False:
        raise ValueError("pre-H021 evidence cannot allow portfolio eligibility")
    if comparison.get("hypothesis_id") != "H021":
        raise ValueError("comparison must be H021")
    if comparison.get("outcomes_opened") is not False:
        raise ValueError("H021 comparison must keep outcomes closed")
    if gate.get("gate_id") != "DR001-H021-TIER-A-GATE-v1":
        raise ValueError("unexpected DR001 H021 gate")
    if gate.get("portfolio_eligibility_allowed") is not False:
        raise ValueError("DR001 H021 gate cannot allow portfolio eligibility")

    pre = _index(pre_evidence.get("companies"), field="symbol", label="pre_evidence")
    revisions = _index(
        comparison.get("revision_observations"),
        field="symbol",
        label="comparison.revision_observations",
    )
    gate_rows = _index(gate.get("companies"), field="symbol", label="gate.companies")

    if set(pre) != EXPECTED_SYMBOLS:
        raise ValueError(f"pre-H021 symbols changed: {sorted(pre)}")
    if not EXPECTED_SYMBOLS.issubset(revisions):
        raise ValueError("H021 comparison is missing Tier A symbols")
    if set(gate_rows) != EXPECTED_SYMBOLS:
        raise ValueError(f"H021 gate symbols changed: {sorted(gate_rows)}")

    rows = []
    for symbol in sorted(EXPECTED_SYMBOLS):
        before = pre[symbol]
        revision = revisions[symbol]
        routed = gate_rows[symbol]
        dependency = before.get("forward_eps_uplift_vs_fy26_trailing_pct")
        if not isinstance(dependency, (int, float)) or isinstance(dependency, bool):
            raise TypeError(f"{symbol}: forward earnings dependency must be numeric")

        rows.append(
            {
                "symbol": symbol,
                "rr001": before.get("rr001"),
                "fq001": before.get("fq001"),
                "nv001": before.get("nv001"),
                "forward_eps_uplift_vs_fy26_trailing_pct": float(dependency),
                "forward_earnings_dependency_state": _dependency_state(float(dependency)),
                "h021": {
                    "prior_capture_date": revision.get("prior_capture_date"),
                    "current_capture_date": revision.get("current_capture_date"),
                    "eps_revision_pct": revision.get("eps_revision_pct"),
                    "primary_signal_available": revision.get("primary_signal_available"),
                    "primary_signal_reason": revision.get("primary_signal_reason"),
                    "primary_top_decile": bool(routed.get("primary_top_decile")),
                    "revision_sign": _revision_sign(
                        revision.get("eps_revision_pct"),
                        revision.get("primary_signal_available"),
                    ),
                },
                "dr001_gate": {
                    "gate_state": routed.get("gate_state"),
                    "research_action": routed.get("research_action"),
                    "valuation_red_team_allowed": routed.get("valuation_red_team_allowed"),
                },
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    dependency_counts = Counter(row["forward_earnings_dependency_state"] for row in rows)
    revision_counts = Counter(row["h021"]["revision_sign"] for row in rows)
    action_counts = Counter(row["dr001_gate"]["research_action"] for row in rows)

    return {
        "schema_version": 1,
        "pack_id": PACK_ID,
        "classification": "RESEARCH_EVIDENCE_PACK_NOT_RETURN_FORECAST",
        "pre_h021_pack_id": pre_evidence["pack_id"],
        "prior_capture_date_ist": comparison.get("prior_capture_date_ist"),
        "current_capture_date_ist": comparison.get("current_capture_date_ist"),
        "dependency_state_counts": dict(sorted(dependency_counts.items())),
        "revision_sign_counts": dict(sorted(revision_counts.items())),
        "research_action_counts": dict(sorted(action_counts.items())),
        "companies": rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
