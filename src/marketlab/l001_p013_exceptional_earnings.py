"""L001 P013: company-reported exceptional PBT components across all 100.

No after-tax normalized earnings invented. Exceptional accounting labels are
disclosed by issuers but do not establish recurrence or economic valuation.
This investigation was designed *after* observing the October 2026 quarter,
so it cannot become an original HG009 frozen score.
"""

from __future__ import annotations

import math

from marketlab.alpha import AlphaContractError, digest

P007_SHA256 = "ade5ea8f0d1e491fba4416443a8c5831b69cbbae81f6479bec61cfbba0e0c276"
P007_ID = "L001-P007-ORIGINAL-Q1-OTHER-INCOME-TRIAGE-ALL100-v1"


def analyze_exceptional_original(original: dict) -> dict:
    unsigned = {key: value for key, value in original.items() if key != "report_sha256"}
    if (
        original.get("report_sha256") != P007_SHA256
        or digest(unsigned) != P007_SHA256
        or original.get("report_id") != P007_ID
        or original.get("original_quarter_xbrl_hashes_verified") != 100
        or original.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("sealed original Q1 earnings evidence altered")
    source_rows = original.get("companies")
    if not isinstance(source_rows, list) or len(source_rows) != 100:
        raise AlphaContractError("original full 100 issuer Q1 source missing")
    seen = set()
    results = []
    for row in source_rows:
        identity = (row.get("symbol"), row.get("isin"))
        if (
            identity in seen or not isinstance(identity[0], str) or not identity[0]
            or not isinstance(identity[1], str) or len(identity[1]) != 12
            or not isinstance(row.get("original_quarter_sha256"), str)
            or len(row["original_quarter_sha256"]) != 64
        ):
            raise AlphaContractError("original issuer identity missing or duplicate")
        seen.add(identity)
        f = row.get("q1_original_income_facts_cr")
        if not isinstance(f, dict):
            raise AlphaContractError("original quarterly financial cells missing")
        names = (
            "exceptional_items_before_tax",
            "profit_before_exceptional",
            "profit_before_tax",
            "profit_loss_for_period",
        )
        cells = [f.get(k) for k in names]
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in cells):
            raise AlphaContractError("original quarterly financial cells not ready")
        exceptional, pre, pbt, pat = cells
        if not math.isclose(pre + exceptional, pbt, rel_tol=0, abs_tol=0.00001):
            raise AlphaContractError("original PBT exceptional bridge does not reconcile")
        positive_pbt_share = (
            round(100 * exceptional / pbt, 6)
            if exceptional > 0 and pbt > 0 else None
        )
        if positive_pbt_share is not None and positive_pbt_share >= 50:
            state = "POSITIVE_EXCEPTIONAL_EXCEEDS_HALF_REPORTED_PBT"
        elif exceptional < 0:
            state = "NEGATIVE_EXCEPTIONAL_OR_CHARGE"
        elif exceptional > 0 and pbt <= 0:
            state = "POSITIVE_EXCEPTIONAL_BUT_REPORTED_PBT_NONPOSITIVE"
        elif exceptional > 0:
            state = "OTHER_POSITIVE_EXCEPTIONAL"
        else:
            state = "ZERO_EXCEPTIONAL"
        results.append({
            "symbol": identity[0], "isin": identity[1],
            "original_quarter_sha256": row["original_quarter_sha256"],
            "q1fy27_reported_pbt_cr": pbt,
            "q1fy27_pbt_before_exceptional_cr": pre,
            "q1fy27_exceptional_item_before_tax_cr": exceptional,
            "q1fy27_reported_pat_cr_not_normalized": pat,
            "exceptional_to_positive_pbt_pct_if_valid": positive_pbt_share,
            "exceptional_observation_state": state,
            "tax_effect_of_exceptional_not_reconciled": True,
            "after_tax_normalized_profit": None,
            "assumed_nonrecurring_by_code": False,
            "posthoc_selection_not_frozen_alpha": True,
            "expected_return": None,
            "investment_authorized": False,
        })
    results.sort(key=lambda r: (r["symbol"], r["isin"]))
    material = [
        r["symbol"] for r in results if r["exceptional_observation_state"]
        == "POSITIVE_EXCEPTIONAL_EXCEEDS_HALF_REPORTED_PBT"
    ]
    output = {
        "schema_version": 1,
        "report_id": "L001-P013-ORIGINAL-Q1-EXCEPTIONAL-PROFIT-CAUTION-v1",
        "original_p007_sha256": P007_SHA256,
        "issuer_count": 100,
        "original_q1_reporting_period": "2026-06-30",
        "source_original_sealed_before_this_research": True,
        "nonzero_exceptional_count": sum(
            r["q1fy27_exceptional_item_before_tax_cr"] != 0 for r in results
        ),
        "material_positive_exceptional_gt_half_pbt_symbols": material,
        "all_original_issuer_identities_preserved": True,
        "decision_threshold_is_posthoc_research_not_a_frozen_factor": True,
        "financial_income_and_capital_gains_not_assumed_nonrecurring": True,
        "earnings_forecasts_generated": False,
        "live_capital_allowed": False,
        "companies": results,
    }
    output["report_sha256"] = digest(output)
    return output
