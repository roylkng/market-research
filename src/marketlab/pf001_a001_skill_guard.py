"""PF001 A001: distinguish mathematical benchmark spread from stock-selection skill.

Read exact original 2026-10-19 paper-fund states and attribution plus dated
immutable summaries. The historical PF001 v1 information ratios are preserved;
an all-cash market-relative advantage must NOT be promoted to stock alpha.
The separate development book has an unclosed position, which likewise does
not provide a realized, independent stock-selection track record.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.attribution import summarize_attribution
from marketlab.paperfund_state import validate_fund_state

AUDIT_ID = "PF001-A001-20261021-CASH-AND-SELECTION-SKILL-ADMISSION-v1"
AS_OF = "2026-10-19"
REVIEW_DATE = "2026-10-21"
ROOT = Path("research/paper-funds/PF001")
SNAPSHOT = ROOT / "audits" / "snapshots" / AS_OF

# Exact originals from main commit e91133400ff5028a4f638f21a566be65b843debd.
# All four original v1 fund/attribution states were snapshotted byte-for-byte.
PINNED = {
    "VALIDATION_FUND": (
        SNAPSHOT / "prospective-validation-state.json",
        "a6633d8a5bcce0d249a728c0fe4737c7b55f8a23",
    ),
    "VALIDATION_ATTRIBUTION": (
        SNAPSHOT / "prospective-validation-attribution.json",
        "9a418f574dffc60173ec927e7603149e9a8af024",
    ),
    "DEVELOPMENT_FUND": (
        SNAPSHOT / "development-state.json",
        "f799a64366bd1c742ccaabe2c388a94d651a99a5",
    ),
    "DEVELOPMENT_ATTRIBUTION": (
        SNAPSHOT / "development-attribution.json",
        "2ef324312a3bb9a5c48e5f9dfd4a820e9abba34d",
    ),
    "VALIDATION_SUMMARY": (
        ROOT / "runs" / AS_OF / "validation-attribution-summary.json",
        "78e08d23ff93e5827479195094508c686e42bff9",
    ),
    "DEVELOPMENT_SUMMARY": (
        ROOT / "runs" / AS_OF / "development-attribution-summary.json",
        "44447c2c32f6b817c6f96b0b200b3d32bf40f8",
    ),
}


def _blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def load_source_receipts(
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]]]:
    sources = {}
    receipts = {}
    for key, (path, expected_blob) in PINNED.items():
        raw = (repo_root / path).read_bytes()
        if _blob(raw) != expected_blob:
            raise AlphaContractError(f"PF001 A001 original {key} source drift")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise AlphaContractError(f"PF001 A001 expected {key} object")
        sources[key] = value
        receipts[key] = {
            "original_repo_path": str(path),
            "original_git_blob_sha": expected_blob,
            "original_raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return sources, receipts


def _finite(value: Any, field: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise AlphaContractError(f"PF001 A001 non-finite {field}")
    return float(value)


def _evaluate_book(
    *,
    name: str,
    state: dict[str, Any],
    attribution: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_fund_state(state)
    if errors:
        raise AlphaContractError(f"PF001 A001 source fund state corrupt: {errors}")
    if (
        state.get("book") != name
        or attribution.get("book") != name
        or state.get("fund_id") != attribution.get("fund_id")
        or summary.get("fund_id") != state.get("fund_id")
        or state.get("last_session_date") != AS_OF
        or attribution.get("last_session_date") != AS_OF
        or attribution.get("last_fund_event_seq") != len(state["events"])
        or state.get("live_capital_allowed") is not False
        or attribution.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("PF001 A001 historic fund/attribution identity drift")

    recomputed = summarize_attribution(attribution)
    if recomputed != summary:
        raise AlphaContractError("PF001 A001 legacy attribution not reproducible")
    history = attribution.get("nav_history")
    if not isinstance(history, list) or len(history) != summary["sessions"]:
        raise AlphaContractError("PF001 A001 broken original daily NAV path")
    positions = state.get("open_positions")
    if not isinstance(positions, dict):
        raise AlphaContractError("PF001 A001 original open-position state missing")
    closed = state.get("closed_positions")
    if not isinstance(closed, list):
        raise AlphaContractError("PF001 A001 original closed-position state missing")
    entries = [row for row in state["events"] if row["event_type"] == "ENTRY_FILLED"]
    if (
        len(attribution["position_benchmarks"]) != len(entries)
        or summary["closed_positions"] != len(closed)
        or summary["closed_positions"] != len(
            attribution["closed_position_attribution"]
        )
        or summary["benchmark"]["basis"] != "PRICE"
        or summary["benchmark"]["dividend_mismatch"] is not True
    ):
        raise AlphaContractError("PF001 A001 v1 attribution and original trades drift")

    cash_weights = [_finite(x["cash_weight"], "daily cash weight") for x in history]
    if not all(0 <= x <= 1.000001 for x in cash_weights):
        raise AlphaContractError("PF001 A001 cash weight out of range")
    cash_fraction = _finite(summary["average_cash_weight"], "average cash")
    if not math.isclose(
        cash_fraction, sum(cash_weights) / len(cash_weights),
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise AlphaContractError("PF001 A001 average cash source drift")

    original_net_active = _finite(summary["net_active_pp"], "net active")
    raw_ir = _finite(summary["information_ratio"], "legacy information ratio")
    benchmark = _finite(summary["benchmark_return"], "benchmark return")
    net_return = _finite(summary["net_portfolio_return"], "net fund return")
    if abs(original_net_active - (net_return - benchmark) * 100) > 1e-9:
        raise AlphaContractError("PF001 A001 active benchmark arithmetic altered")

    if name == "PROSPECTIVE_VALIDATION":
        if (
            entries or positions or closed
            or not all(math.isclose(x, 1, abs_tol=1e-12) for x in cash_weights)
            or not math.isclose(net_return, 0, abs_tol=1e-12)
        ):
            raise AlphaContractError(
                "PF001 A001 validation is not original 100-percent-cash book"
            )
        state_label = "NO_STOCK_SELECTION_OBSERVATIONS_CASH_ONLY"
        realized_skill = None
        conditional_cash_active = original_net_active
    elif name == "DEVELOPMENT":
        # Current development exposure is real in the paper model but is
        # extremely cash-heavy and has no CLOSED stock-position outcomes.
        if len(entries) != 1 or len(positions) != 1 or closed:
            raise AlphaContractError("PF001 A001 development trade count drift")
        state_label = "UNMATURED_SINGLE_PAPER_POSITION_NO_REALIZED_SELECTION_SKILL"
        realized_skill = None
        conditional_cash_active = None
    else:
        raise AlphaContractError("PF001 A001 unknown paper-fund book")

    return {
        "book": name,
        "source_attribution_id": summary["attribution_id"],
        "observed_session_count": len(history),
        "entry_filled_event_count": len(entries),
        "open_paper_stock_positions": len(positions),
        "closed_paper_stock_positions": len(closed),
        "average_cash_weight": cash_fraction,
        "estimated_average_paper_stock_exposure_fraction": round(
            1 - cash_fraction, 10
        ),
        "source_benchmark_price_index_return_fraction": benchmark,
        "source_net_fund_return_fraction": net_return,
        "legacy_benchmark_relative_active_pp": original_net_active,
        "legacy_information_ratio_NOT_stock_selection": raw_ir,
        "cash_avoidance_active_pp_if_all_cash": conditional_cash_active,
        "realized_stock_selection_excess_return_pp": realized_skill,
        "stock_selection_skill_information_ratio": None,
        "stock_selection_skill_win_rate": None,
        "original_closed_position_count_for_selection_inference": len(closed),
        "interpretation_state": state_label,
        "stock_selection_skill_statistically_supported": False,
        "strategy_could_have_had_executable_fills": False,
        "accounting_and_sector_exposure_adjusted": False,
        "cash_benchmark_interest_rate_captured": False,
        "risk_free_cash_return_not_assumed": True,
        "benchmark_TRI_comparable": False,
        "investment_approval_or_live_trading": False,
    }


def build_pf001_a001(
    sources: dict[str, dict],
    receipts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    if set(sources) != set(PINNED) or set(receipts) != set(PINNED):
        raise AlphaContractError("PF001 A001 original six evidence objects incomplete")
    validated = _evaluate_book(
        name="PROSPECTIVE_VALIDATION",
        state=sources["VALIDATION_FUND"],
        attribution=sources["VALIDATION_ATTRIBUTION"],
        summary=sources["VALIDATION_SUMMARY"],
    )
    development = _evaluate_book(
        name="DEVELOPMENT",
        state=sources["DEVELOPMENT_FUND"],
        attribution=sources["DEVELOPMENT_ATTRIBUTION"],
        summary=sources["DEVELOPMENT_SUMMARY"],
    )
    output = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "review_date": REVIEW_DATE,
        "original_history_last_session": AS_OF,
        "classification": (
            "SOURCE_BOUND_CASH_AVOIDANCE_NOT_VERIFIED_STOCK_SELECTION_ALPHA"
        ),
        "original_main_anchoring_commit": (
            "e91133400ff5028a4f638f21a566be65b843debd"
        ),
        "original_snapshots_copied_byte_for_byte": True,
        "original_source_git_blob_receipts": receipts,
        "validation": validated,
        "development": development,
        "recomputed_v1_raw_active_uses_mathematical_market_benchmark": True,
        "v1_information_ratio_is_not_invalid_math": True,
        "v1_information_ratio_does_not_measure_stock_selection_skill": True,
        "old_v1_snapshots_unmodified": True,
        "requires_separate_cash_or_risk_free_benchmark": True,
        "requires_independent_realized_or_matured_paper_trades": True,
        "requires_time_alignment_corporate_actions_costs_before_alpha": True,
        "positive_stock_selection_alpha_evidence": False,
        "confidence_in_50pct_annual_returns_supported": False,
        "portfolio_investment_recommendations_generated": False,
        "live_capital_allowed": False,
    }
    output["audit_sha256"] = digest(output)
    return output


def materialize_pf001_a001(root: Path) -> dict[str, Any]:
    evidence, receipts = load_source_receipts(root)
    return build_pf001_a001(evidence, receipts)


def validate_pf001_a001(output: dict[str, Any], root: Path) -> None:
    unsigned = copy.deepcopy(output)
    sha = unsigned.pop("audit_sha256", None)
    if sha != digest(unsigned):
        raise AlphaContractError("PF001 A001 audit SHA changed")
    if output != materialize_pf001_a001(root):
        raise AlphaContractError("PF001 A001 original source replay differs")
