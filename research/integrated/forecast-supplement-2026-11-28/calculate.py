#!/usr/bin/env python3
"""Additive, research-only evaluation. Never edits a forecast or fetches outcomes.

python calculate.py
python calculate.py actuals.json --as-of 2027-02-28T18:00:00Z

Actual rows require isin, symbol, scope, target, period_end, actual_pat_cr,
unit='INR_CRORE', first_release_date, source_url, reviewed_at_utc and
source_review_status='FIRST_REPORTED_QUARTER_SOURCE_CHECKED'. That status is a
manual evidence assertion, not source authentication performed by this script.
"""

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

IST = timezone(timedelta(hours=5, minutes=30))
IDENTITY = ("symbol", "isin", "scope", "target")
PERIODS = ("q1", "q2", "prior_q2", "prior_q3")
FROZEN_METHODS = ("latest_quarter", "two_quarter_mean", "damped_sequential", "accounting_driver")
SOURCE_METHODS = (
    "latest_verified_quarter", "verified_two_quarter_mean", "verified_damped_sequential",
    "seasonal_naive", "seasonal_additive", "normalized_seasonal_additive",
    "raw_yoy_trend", "normalized_yoy_trend",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def number(obj, key):
    value = obj.get(key)
    require(finite(value), f"Missing or nonfinite numeric field: {key}")
    return value


def day(value):
    require(isinstance(value, str), "Date must be an ISO calendar date")
    parsed = date.fromisoformat(value)
    require(parsed.isoformat() == value, "Date must have YYYY-MM-DD format")
    return parsed


def instant(value):
    require(isinstance(value, str) and "T" in value, "Timestamp must include date, time and timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "Naive timestamp")
    return parsed.astimezone(timezone.utc)


def https_url(value):
    require(isinstance(value, str), "Source URL must be text")
    parsed = urlparse(value)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password,
            "Source must be a valid HTTPS URL without embedded credentials")


def validate_baseline_bytes(original_bytes, packet, selection):
    """Enforce the new supplement's pin without modifying the old packet."""
    expected = selection.get("baseline_sha256")
    require(isinstance(expected, str) and len(expected) == 64 and
            all(c in "0123456789abcdef" for c in expected), "Missing valid baseline SHA256 pin")
    observed = hashlib.sha256(original_bytes).hexdigest()
    require(observed == expected, "Original register SHA256 differs from frozen supplement pin")
    if packet.get("original_register_sha256") is not None:
        require(packet["original_register_sha256"] == expected, "Register and selection baseline pins conflict")
    return observed


def predict_model(model):
    """Reported group PAT minus NCI, with associates supplied after tax."""
    require(isinstance(model, dict), "Forecast requires an explicit arithmetic model")
    kind = model.get("kind")
    if kind == "pbt_margin":
        pbt = number(model, "revenue_cr") * number(model, "pbt_margin")
        pbt += number(model, "exceptional_pretax_cr")
    elif kind == "operating":
        pbt = number(model, "revenue_cr") * number(model, "ebit_margin")
        pbt += number(model, "other_income_cr") - number(model, "finance_cost_cr")
        pbt += number(model, "exceptional_pretax_cr")
    elif kind == "pbt_components":
        components = model.get("components")
        require(isinstance(components, list) and components, "Named PBT components required")
        require(all(isinstance(c.get("name"), str) and c["name"] for c in components), "Unnamed PBT component")
        pbt = sum(number(c, "amount_cr") for c in components)
    else:
        raise ValueError(f"Unsupported model kind: {kind}")
    tax_rate = number(model, "tax_rate")
    require(0 <= tax_rate <= 1, "Tax rate outside [0,1]")
    # For a loss, tax benefit is an explicit scenario assumption, not automatic evidence.
    after_tax = pbt * (1 - tax_rate)
    associates = number(model, "associates_after_tax_cr")
    nci = number(model, "nci_cr")
    pat = after_tax + associates - nci
    require(finite(pat), "Nonfinite model result")
    return {"pbt_cr": pbt, "tax_cr": pbt * tax_rate,
            "associates_after_tax_cr": associates, "nci_cr": nci, "owner_pat_cr": pat}


def validate_scenarios(case):
    scenarios = case.get("scenarios")
    if scenarios is None:
        return None
    require(case["status"] == "FORECAST", "Abstention cannot carry forecast scenarios")
    order = ["adverse", "base", "favorable"]
    require(case.get("scenario_order") == order, "Scenario ordering must be explicitly adverse/base/favorable")
    require(isinstance(scenarios, dict) and set(scenarios) == set(order), "Exactly three named scenarios required")
    calculated = {}
    for name in order:
        spec = scenarios[name]
        result = predict_model(spec.get("model"))
        published = spec.get("forecast_pat_cr")
        require(finite(published) and math.isclose(published, result["owner_pat_cr"], rel_tol=1e-9, abs_tol=1e-6),
                f"Published {name} scenario does not reproduce")
        calculated[name] = result
    require(scenarios["base"]["model"] == case["model"], "Scenario base model differs from primary forecast")
    pats = [calculated[name]["owner_pat_cr"] for name in order]
    require(pats[0] <= pats[1] <= pats[2], "Scenario PAT ordering contradicts adverse/base/favorable labels")
    return calculated


def sourced_baselines(case, ratio_floor_cr=1.0):
    out = dict.fromkeys(SOURCE_METHODS)
    reasons = {}
    if not case["source_valid"]:
        return out, {"all": "Matching quarterly source inputs not validated"}
    q = case["verified_pat_cr"]
    q1, q2, p2, p3 = [q.get(p) for p in PERIODS]
    out["latest_verified_quarter"] = q2
    out["verified_two_quarter_mean"] = (q1 + q2) / 2
    out["verified_damped_sequential"] = q2 + .25 * (q2 - q1)
    if finite(p3):
        out["seasonal_naive"] = p3
    if finite(p2) and finite(p3):
        out["seasonal_additive"] = q2 + p3 - p2
        if p2 >= ratio_floor_cr and p2 > 0:
            out["raw_yoy_trend"] = p3 * q2 / p2
        else:
            reasons["raw_yoy_trend"] = "Prior Q2 PAT below fixed positive denominator floor"
        adjustments = case.get("normalization_adjustments_cr", {})
        if all(finite(adjustments.get(p)) for p in ("q2", "prior_q2", "prior_q3")):
            n2 = q2 + adjustments["q2"]
            np2 = p2 + adjustments["prior_q2"]
            np3 = p3 + adjustments["prior_q3"]
            out["normalized_seasonal_additive"] = n2 + np3 - np2
            if np2 >= ratio_floor_cr and np2 > 0:
                out["normalized_yoy_trend"] = np3 * n2 / np2
            else:
                reasons["normalized_yoy_trend"] = "Normalized prior Q2 below fixed positive denominator floor"
        else:
            reasons["normalized"] = "Explicit normalization inputs unavailable"
    else:
        reasons["seasonal_comparison"] = "Matching prior-year Q2 and Q3 not both verified"
    return out, reasons


def validate_packet(packet, original, selection):
    cutoff = instant(packet["evidence_cutoff_utc"])
    target_end = day(packet["target_period_end"])
    require(target_end == day(original["target_period_end"]), "Target changed from frozen cohort")
    require(cutoff.astimezone(IST).date() <= target_end, "Supplement created after target quarter ended")
    require(day(packet["research_date_ist"]) == cutoff.astimezone(IST).date(), "Research date/cutoff mismatch")
    attempts = selection["attempted"]
    old_assisted = {x["isin"] for x in original["assisted"]}
    expected = [r for r in original["roster"]["selected"] if r["isin"] not in old_assisted][:len(attempts)]
    require(len(attempts) == 12, "Frozen attempted denominator changed")
    require([{k: r[k] for k in (*IDENTITY, "rank")} for r in attempts]
            == [{k: r[k] for k in (*IDENTITY, "rank")} for r in expected], "Attempted cohort substituted/reordered")
    cases = packet["cases"]
    require(len(cases) == len(attempts), "Every attempted name must retain one forecast or abstention")
    case_map = {c["isin"]: c for c in cases}
    require(len(case_map) == len(cases), "Duplicate case")
    for row in attempts:
        require(row["isin"] in case_map, "Missing attempted case")
        c = case_map[row["isin"]]
        require(all(c.get(k) == row[k] for k in IDENTITY), "Case identity/scope/target mismatch")
        require(c.get("status") in ("FORECAST", "ABSTAIN"), "Invalid case status")
        require(isinstance(c.get("source_valid"), bool), "source_valid must be a boolean")
        require(isinstance(c.get("source_review_status"), str) and c["source_review_status"], "Source status missing")
        q = c.get("verified_pat_cr", {})
        require(all(q.get(p) is None or finite(q[p]) for p in PERIODS), "Invalid verified PAT")
        adjustments = c.get("normalization_adjustments_cr", {})
        require(all(v is None or finite(v) for v in adjustments.values()), "Invalid normalization adjustment")
        if any(finite(v) and v != 0 for v in adjustments.values()):
            require(bool(c.get("normalization_basis")), "Nonzero normalization requires rationale")
        sources = c.get("sources", [])
        for s in sources:
            https_url(s["url"])
            observed = instant(s["observed_at_utc"])
            require(observed <= cutoff, "Source observed after evidence cutoff")
            if s.get("publication_date") is not None:
                published = day(s["publication_date"])
                require(published <= observed.astimezone(IST).date(), "Source observed before publication")
        if c["source_valid"]:
            require(finite(q.get("q1")) and finite(q.get("q2")) and bool(sources), "Validated source inputs incomplete")
        if c["status"] == "FORECAST":
            require(c["source_valid"], "Cannot issue model forecast on unvalidated matching inputs")
            calculated = predict_model(c.get("model"))
            if c.get("forecast_pat_cr") is not None:
                require(finite(c["forecast_pat_cr"]) and math.isclose(calculated["owner_pat_cr"], c["forecast_pat_cr"], rel_tol=1e-9, abs_tol=1e-6), "Published forecast does not reproduce")
        else:
            require(bool(c.get("abstention_reason")), "Abstention requires a reason")
            require(c.get("model") is None and c.get("forecast_pat_cr") is None, "Abstention carries a hidden prediction")
        validate_scenarios(c)
    return cutoff, case_map


def validate_actuals(actuals, original, as_of):
    require(isinstance(actuals, list), "Actuals must be an array")
    ids = {r["isin"]: r for r in original["predictions"]}
    result = {}
    for a in actuals:
        row = ids.get(a.get("isin"))
        require(row is not None and a["isin"] not in result, "Unknown or duplicate actual")
        require(all(a.get(k) == row[k] for k in IDENTITY), "Actual identity/scope/target mismatch")
        require(a.get("period_end") == original["target_period_end"], "Wrong actual period")
        require(a.get("unit") == "INR_CRORE", "Explicit INR_CRORE units required")
        require(finite(a.get("actual_pat_cr")), "Invalid actual value")
        published = day(a["first_release_date"])
        reviewed = instant(a["reviewed_at_utc"])
        require(day(original["target_period_end"]) < published <= reviewed.astimezone(IST).date(), "Invalid release/review chronology")
        require(reviewed <= as_of and published <= as_of.astimezone(IST).date(), "Outcome evidence after evaluation cutoff")
        require(a.get("source_review_status") == "FIRST_REPORTED_QUARTER_SOURCE_CHECKED", "First reported quarterly source must be reviewed")
        https_url(a["source_url"])
        result[a["isin"]] = a
    return result


def compare(rows, lhs, rhs):
    available = [r for r in rows if finite(r["forecasts"].get(lhs)) and finite(r["forecasts"].get(rhs))]
    matched = [r for r in available if r["errors"] is not None]
    n = len(matched)
    base = {"lhs": lhs, "rhs": rhs, "available_pairs": len(available), "matured_pairs": n,
            "missing_pairs": len(available)-n, "mean_lhs_scaled_abs": None, "mean_rhs_scaled_abs": None,
            "mean_paired_improvement": None, "mean_lhs_signed_scaled": None, "wins": None, "ties": None, "losses": None}
    if not n:
        return base
    le = [r["errors"][lhs]["scaled_abs"] for r in matched]
    re = [r["errors"][rhs]["scaled_abs"] for r in matched]
    wins = sum(l < r - 1e-12 for l, r in zip(le, re))
    ties = sum(abs(l-r) <= 1e-12 for l, r in zip(le, re))
    return {**base, "mean_lhs_scaled_abs": sum(le)/n, "mean_rhs_scaled_abs": sum(re)/n,
            "mean_paired_improvement": sum(r-l for l, r in zip(le, re))/n,
            "mean_lhs_signed_scaled": sum(r["errors"][lhs]["signed_scaled"] for r in matched)/n,
            "wins": wins, "ties": ties, "losses": n-wins-ties}


def score(packet, original, selection, actuals=None, as_of=None):
    cutoff, cases = validate_packet(packet, original, selection)
    clock = instant(as_of) if as_of else cutoff
    require(clock >= cutoff, "Evaluation cutoff precedes forecast evidence cutoff")
    actual_map = validate_actuals(packet.get("actuals", []) if actuals is None else actuals, original, clock)
    ids = {r["isin"]: r for r in original["predictions"]}
    old_rows = {r["isin"]: r for r in original["roster"]["selected"]}
    ratio_floor = packet.get("ratio_denominator_floor_cr", 1.0)
    require(finite(ratio_floor) and ratio_floor > 0, "Positive ratio denominator floor required")
    rows = []
    for identity in selection["attempted"]:
        key = identity["isin"]
        c, old, raw = cases[key], ids[key], old_rows[key]
        forecasts = {"frozen_"+k: old["forecasts"].get(k) for k in FROZEN_METHODS}
        fresh, abstentions = sourced_baselines(c, ratio_floor)
        forecasts.update(fresh)
        model = predict_model(c["model"]) if c["status"] == "FORECAST" else None
        forecasts["assisted_driver"] = model["owner_pat_cr"] if model else None
        repair = {}
        if c["source_valid"]:
            for period in ("q1", "q2"):
                original_pat = raw["periods"][period][raw["pat_key"]]
                verified_pat = c["verified_pat_cr"][period]
                repair[period] = {"original_pat_cr": original_pat, "verified_pat_cr": verified_pat,
                                  "difference_cr": verified_pat-original_pat,
                                  "exceeds_original_bridge_tolerance": abs(verified_pat-original_pat) > original["config"]["bridgeToleranceCr"]}
        actual = actual_map.get(key)
        scale = old["scale_cr"]
        errors = None if actual is None else {k: {"signed_cr": v-actual["actual_pat_cr"],
                                                 "signed_scaled": (v-actual["actual_pat_cr"])/scale,
                                                 "scaled_abs": abs(v-actual["actual_pat_cr"])/scale}
                                            for k, v in forecasts.items() if finite(v)}
        rows.append({**{k: c[k] for k in IDENTITY}, "status": c["status"], "source_valid": c["source_valid"],
                     "original_scale_cr": scale, "source_input_comparison": repair, "forecasts": forecasts,
                     "model_calculation": model, "scenario_calculations": validate_scenarios(c),
                     "comparator_abstentions": abstentions,
                     "actual": actual, "errors": errors})
    methods = ["frozen_"+k for k in FROZEN_METHODS]+list(SOURCE_METHODS)+["assisted_driver"]
    coverage = {m: {"forecasted": sum(finite(r["forecasts"].get(m)) for r in rows),
                    "matured": sum(r["actual"] is not None and finite(r["forecasts"].get(m)) for r in rows)} for m in methods}
    return {
        "classification": "ADDITIVE_FUNDAMENTAL_FORECAST_COMPARISON_NOT_STOCK_RETURNS_OR_VALIDATED_SKILL",
        "evaluation_as_of_utc": clock.isoformat(),
        "coverage": {"original_cohort": len(original["predictions"]), "attempted": len(rows),
                     "source_valid": sum(r["source_valid"] for r in rows),
                     "assisted_forecasted": coverage["assisted_driver"]["forecasted"],
                     "abstained": sum(r["status"] == "ABSTAIN" for r in rows),
                     "source_input_difference_over_original_tolerance": sum(any(v["exceeds_original_bridge_tolerance"] for v in r["source_input_comparison"].values()) for r in rows),
                     "original_cohort_actuals_observed": len(actual_map),
                     "attempted_actuals_observed": sum(r["actual"] is not None for r in rows),
                     "assisted_actuals_observed": coverage["assisted_driver"]["matured"],
                     "attempted_actuals_missing": sum(r["actual"] is None for r in rows)},
        "primary_comparison": compare(rows, "assisted_driver", "normalized_seasonal_additive"),
        "source_matched_comparisons": [compare(rows, "assisted_driver", m) for m in SOURCE_METHODS],
        "different_information_cutoff_comparisons": [compare(rows, "assisted_driver", "frozen_"+m) for m in FROZEN_METHODS],
        "source_repair_diagnostic": compare(rows, "latest_verified_quarter", "frozen_latest_quarter"),
        "method_coverage": coverage, "rows": rows,
        "limits": ["First-release source review is a human/researcher assertion, not automated authentication.",
                   "Frozen and fresh-source forecasts use different information cutoffs. Their difference is not pure reasoning value.",
                   "Normalized comparators inherit explicit analyst one-off assumptions. Ranges are scenarios, not calibrated prediction intervals.",
                   "Every method comparison uses exactly the same available observed issuers and the original per-issuer scale.",
                   "One quarter and this selected acquisition universe do not establish an investment edge or independent repeated trials."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actuals", nargs="?", help="Reviewed first-release outcome JSON array")
    parser.add_argument("--as-of", help="UTC/offset timestamp for an outcome evaluation")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    packet = json.loads((root / "forecast_register.json").read_text())
    original_path = (root / packet.get("original_register", "../forecast-scale-2026-11-27/forecast_register.json")).resolve()
    original_bytes = original_path.read_bytes()
    selection = json.loads((root / packet.get("selection_file", "selection.json")).read_text())
    digest = validate_baseline_bytes(original_bytes, packet, selection)
    original = json.loads(original_bytes)
    actuals = json.loads(Path(args.actuals).read_text()) if args.actuals else None
    result = score(packet, original, selection, actuals, args.as_of)
    result["original_register_sha256_verified"] = digest
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
