"""Outcome-blind H021 EPS revision sign-semantics audit.

The frozen H021 ratio (current / prior - 1) REVERSES the sign of the
underlying absolute EPS change whenever prior consensus EPS is negative.
This diagnostic preserves the existing H021 selections and never substitutes
a new return-predictive signal.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.h021_capture import CANONICAL_UNIVERSE_BLOB_SHA
from marketlab.h021_legacy_adapter import load_h021_capture_compatible

AUDIT_ID = "H021-P007-2026-10-09-EPS-SIGN-SEMANTICS-v1"
COMPARE_ID = "28-35 day same-period consensus EPS revision"
COMPARISON_PATH = Path(
    "research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json"
)
PRIOR_PATH = Path(
    "research/prospective/h021/captures/2026-09-11-full-u001-v1.json.gz"
)
CURRENT_PATH = Path(
    "research/prospective/h021/captures/2026-10-09-full-u001-v1.json.gz"
)
UNIVERSE_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
BATCH_PATH = Path("research/prospective/h021/capture-batches-v1.json")
SOURCE_DATES = ("2026-09-11", "2026-10-09")


def _source_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _load_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise TypeError(f"expected JSON object at {path}")
    return obj


def _index(rows: object, name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != 100:
        raise ValueError(f"{name} must preserve 100 frozen symbols")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"{name} entry must be object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in indexed:
            raise ValueError(f"{name} symbol missing or duplicated")
        indexed[symbol] = row
    return indexed


def _finite_number(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(float(value))


def _sign(value: float) -> str:
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "ZERO"


def _financial_state(prior: float, current: float) -> str:
    if prior < 0 and current < 0:
        return "LOSS_TO_LOSS"
    if prior < 0 and current >= 0:
        return "LOSS_TO_BREAK_EVEN_OR_PROFIT"
    if prior > 0 and current < 0:
        return "PROFIT_TO_LOSS"
    if prior > 0 and current >= 0:
        return "PROFIT_TO_BREAK_EVEN_OR_PROFIT"
    raise ValueError("prior EPS zero cannot form a valid H021 primary signal")


def build_eps_sign_audit(
    comparison: dict[str, Any],
    prior: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    if comparison.get("schema_version") != 1 or comparison.get("hypothesis_id") != "H021":
        raise ValueError("H021 comparison identity invalid")
    if comparison.get("primary_signal") != COMPARE_ID:
        raise ValueError("frozen H021 primary signal changed")
    if (
        comparison.get("prior_capture_date_ist") != SOURCE_DATES[0]
        or comparison.get("current_capture_date_ist") != SOURCE_DATES[1]
        or comparison.get("capture_interval_days") != 28
    ):
        raise ValueError("unexpected first H021 comparison pair")
    if comparison.get("universe_git_blob_sha") != CANONICAL_UNIVERSE_BLOB_SHA:
        raise ValueError("unexpected U001 source universe")
    if (
        comparison.get("outcomes_opened") is not False
        or comparison.get("live_capital_allowed") is not False
    ):
        raise ValueError("H021 study must remain outcome-blind and research-only")
    for snapshot, day in ((prior, SOURCE_DATES[0]), (current, SOURCE_DATES[1])):
        if (
            snapshot.get("hypothesis_id") != "H021"
            or snapshot.get("capture_date_ist") != day
            or snapshot.get("outcomes_opened") is not False
            or snapshot.get("live_capital_allowed") is not False
        ):
            raise ValueError("capture identity/date/outcome boundary changed")
    reference = _index(prior.get("observations"), "prior")
    observed = _index(current.get("observations"), "current")
    comparison_rows = _index(comparison.get("revision_observations"), "comparison")
    if set(reference) != set(observed) or set(reference) != set(comparison_rows):
        raise ValueError("H021 comparison lost or substituted a symbol")

    top = comparison.get("primary_top_decile_symbols")
    if (
        not isinstance(top, list)
        or not top
        or len(top) != len(set(top))
        or set(top) - set(comparison_rows)
        or len(top) != comparison.get("primary_top_decile_count")
    ):
        raise ValueError("frozen top-decile identity/count invalid")
    top_set = set(top)
    audited = []
    missing = []
    for symbol in sorted(reference):
        comp = comparison_rows[symbol]
        if comp.get("primary_signal_available") is not True:
            if comp.get("primary_signal_available") is not False:
                raise ValueError("invalid H021 primary availability")
            if symbol in top_set:
                raise ValueError("ineligible symbol cannot enter first H021 top decile")
            missing.append({
                "symbol": symbol, "primary_signal_reason": comp["primary_signal_reason"]
            })
            continue

        before = reference[symbol]
        after = observed[symbol]
        prior_eps = before.get("consensus_eps")
        current_eps = after.get("consensus_eps")
        if not _finite_number(prior_eps) or not _finite_number(current_eps):
            raise ValueError(f"{symbol}: valid primary signal lacks finite source EPS")
        prev = float(prior_eps)
        now = float(current_eps)
        if prev == 0:
            raise ValueError(f"{symbol}: primary denominator EPS is zero")
        if before.get("fiscal_period") != after.get("fiscal_period"):
            raise ValueError(f"{symbol}: source fiscal-period mismatch")
        if before.get("period_ending") != after.get("period_ending"):
            raise ValueError(f"{symbol}: source fiscal-end mismatch")
        if before.get("eps_currency") != after.get("eps_currency"):
            raise ValueError(f"{symbol}: source EPS-currency mismatch")
        if (
            before.get("analyst_count") != comp.get("analyst_count_prior")
            or after.get("analyst_count") != comp.get("analyst_count_current")
        ):
            raise ValueError(f"{symbol}: source analyst-panel identity mismatch")

        ratio_pct = 100.0 * (now / prev - 1.0)
        comparison_pct = comp.get("eps_revision_pct")
        if not _finite_number(comparison_pct) or not math.isclose(
            ratio_pct, float(comparison_pct), rel_tol=1e-9, abs_tol=1e-8
        ):
            raise ValueError(f"{symbol}: EPS source does not reproduce H021 primary ratio")
        delta = now - prev
        inversion = prev < 0 and delta != 0
        if inversion and _sign(ratio_pct) == _sign(delta):
            raise ValueError("algebraic EPS direction inconsistency")
        if not inversion and delta != 0 and _sign(ratio_pct) != _sign(delta):
            raise ValueError("positive-denominator EPS direction inconsistency")
        audited.append({
            "symbol": symbol,
            "selected_by_original_h021_top_decile": symbol in top_set,
            "prior_eps": prev,
            "current_eps": now,
            "eps_currency": before.get("eps_currency"),
            "fiscal_period": before.get("fiscal_period"),
            "fiscal_period_end": before.get("period_ending"),
            "original_ratio_revision_pct": ratio_pct,
            "absolute_eps_change": delta,
            "ratio_revision_direction": _sign(ratio_pct),
            "absolute_eps_change_direction": _sign(delta),
            "negative_prior_eps": prev < 0,
            "ratio_direction_inverted_vs_absolute_eps_change": inversion,
            "financial_state": _financial_state(prev, now),
            "analyst_count_prior": comp.get("analyst_count_prior"),
            "analyst_count_current": comp.get("analyst_count_current"),
            "return_outcomes_opened": False,
        })

    if len(audited) != comparison.get("primary_signal_available_count"):
        raise ValueError("H021 audited EPS coverage changed")
    if {row["symbol"] for row in audited if row["selected_by_original_h021_top_decile"]} != top_set:
        raise ValueError("H021 selected symbols changed")
    inverted = [row for row in audited if row["ratio_direction_inverted_vs_absolute_eps_change"]]
    selected_inverted = [row for row in inverted if row["selected_by_original_h021_top_decile"]]
    states = Counter(row["financial_state"] for row in audited)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "POST_SIGNAL_OUTCOME_BLIND_EPS_ARITHMETIC_AUDIT_NOT_ALPHA",
        "prior_capture_date_ist": SOURCE_DATES[0],
        "current_capture_date_ist": SOURCE_DATES[1],
        "eligible_eps_observations": len(audited),
        "ineligible_rows_retained": missing,
        "original_top_decile_symbols_unchanged": top,
        "prior_eps_negative_count": sum(row["negative_prior_eps"] for row in audited),
        "direction_inversion_count": len(inverted),
        "direction_inversion_top_decile_count": len(selected_inverted),
        "top_decile_inverted_symbols": [row["symbol"] for row in selected_inverted],
        "financial_state_counts": dict(sorted(states.items())),
        "audited_rows": audited,
        "economic_eps_sign_is_new_alpha": False,
        "h021_primary_selection_revised": False,
        "entry_intents_revised": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return payload


def audit_sealed_first_cohort() -> dict[str, Any]:
    universe = _load_json(UNIVERSE_PATH)
    batches = _load_json(BATCH_PATH)
    if universe.get("schema_version") != 1:
        raise ValueError("frozen H021 U001 schema changed")
    prior, prior_manifest = load_h021_capture_compatible(
        PRIOR_PATH, universe=universe, batch_spec=batches
    )
    current, current_manifest = load_h021_capture_compatible(
        CURRENT_PATH, universe=universe, batch_spec=batches
    )
    comp = _load_json(COMPARISON_PATH)
    result = build_eps_sign_audit(comp, prior, current)
    result["source_provenance"] = {
        "comparison_raw_sha256": hashlib.sha256(_source_bytes(COMPARISON_PATH)).hexdigest(),
        "prior_original_gzip_sha256": hashlib.sha256(_source_bytes(PRIOR_PATH)).hexdigest(),
        "current_original_gzip_sha256": hashlib.sha256(_source_bytes(CURRENT_PATH)).hexdigest(),
        "prior_manifest_payload_sha256": prior_manifest["payload_uncompressed_sha256"],
        "current_manifest_payload_sha256": current_manifest["payload_uncompressed_sha256"],
    }
    return result
