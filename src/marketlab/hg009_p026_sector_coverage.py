"""HG009 P026: prove sector source coverage and non-identifiability.

This is a POST-ENTRY source-feasibility audit of the already frozen three-arm
HG009 sample. It does NOT condition the original Oct 15 cohort on a 2026-10-16
industry CSV or retrospectively retrofit an alpha test.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs, verify_hg009_controls
from marketlab.l001_p003_industry_overlap import COLUMNS

REPORT_ID = "HG009-P026-ORIGINAL-SECTOR-COVERAGE-AND-IDENTIFIABILITY-v1"
SOURCE_PATH = Path(
    "research/prospective/rm001-sc002/raw/2026-10-16/"
    "nifty-total-market-692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc.csv"
)
SOURCE_SHA256 = "692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc"
SOURCE_BLOB_SHA = "e92fddc597db848d7580b8b96f738121efbfde1d"
SECTOR_SOURCE_DATE = "2026-10-16"
FROZEN_ENTRY = "2026-10-15"
HG009_SELECTED_SHA = "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5"
HG009_CONTROL_SHA = "8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8"
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
REQUIRED_SOURCE_COVERAGE_FRACTION = 0.95
REQUIRED_PER_ARM_COVERAGE_FRACTION = 0.90


def _check_source(original_csv: bytes) -> dict[tuple[str, str], str]:
    if hashlib.sha256(original_csv).hexdigest() != SOURCE_SHA256:
        raise AlphaContractError("P026 frozen original NSE sector CSV SHA changed")
    git_blob = hashlib.sha1(
        b"blob " + str(len(original_csv)).encode("ascii") + b"\x00"
        + original_csv, usedforsecurity=False,
    ).hexdigest()
    if git_blob != SOURCE_BLOB_SHA:
        raise AlphaContractError("P026 original NSE sector Git source blob changed")
    try:
        decoded = original_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("P026 official NSE CSV invalid UTF8") from exc
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames != list(COLUMNS):
        raise AlphaContractError("P026 NSE original five-column header mismatch")
    all_rows = 0
    by_identity: dict[tuple[str, str], str] = {}
    for row in reader:
        all_rows += 1
        symbol = str(row.get("Symbol") or "").strip()
        isin = str(row.get("ISIN Code") or "").strip()
        industry = str(row.get("Industry") or "").strip()
        series = str(row.get("Series") or "").strip()
        if (
            not symbol or len(isin) != 12 or not industry
            or not row.get("Company Name") or not series
        ):
            raise AlphaContractError("P026 incomplete original sector row")
        if series == "EQ":
            key = (symbol, isin)
            if key in by_identity:
                raise AlphaContractError("P026 duplicate official NSE EQ identity")
            by_identity[key] = industry
    if all_rows != 755 or len(by_identity) != 744:
        raise AlphaContractError("P026 original indexed subset coverage changed")
    return by_identity


def build_sector_identifiability_report(
    *,
    source_csv: bytes,
    router: dict[str, Any],
    selected: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    verify_hg009_controls(controls, source=router, selected=selected)
    if (
        selected.get("cohort_sha256") != HG009_SELECTED_SHA
        or controls.get("manifest_sha256") != HG009_CONTROL_SHA
        or selected.get("selected_count") != 100
        or controls.get("total_unique_observation_identities") != 300
    ):
        raise AlphaContractError("P026 original 300-company cohort identity drift")
    official = _check_source(source_csv)
    original_arms = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    rows = []
    by_arm: dict[str, dict[str, Any]] = {}
    counts = {}
    seen = set()
    for arm in ARMS:
        members = original_arms[arm]
        if len(members) != 100:
            raise AlphaContractError("P026 each frozen arm must remain 100")
        matched = Counter()
        missing = []
        for member in members:
            symbol, isin = member["symbol"], member["isin"]
            key = (symbol, isin)
            if key in seen:
                raise AlphaContractError("P026 repeated symbol/ISIN across arms")
            seen.add(key)
            industry = official.get(key)
            if industry is None:
                missing.append(symbol)
            else:
                matched[industry] += 1
            rows.append({
                "arm": arm,
                "symbol": symbol,
                "frozen_isin": isin,
                "provisional_oct16_index_industry": industry,
                "original_source_join_exact_symbol_isin": industry is not None,
                "source_missing_not_imputed": industry is None,
                "sector_known_at_original_oct15_entry": False,
                "sector_pretrade_model_feature_admitted": False,
                "investment_recommendation": False,
            })
        matched_count = sum(matched.values())
        counts[arm] = matched
        by_arm[arm] = {
            "frozen_members": 100,
            "exact_source_matches": matched_count,
            "not_covered_by_original_index_subset": len(missing),
            "source_match_fraction": matched_count / 100,
            "financial_services_exact_matches": matched.get(
                "Financial Services", 0
            ),
            "matched_industry_counts": dict(sorted(matched.items())),
            "unmatched_original_symbols": sorted(missing),
        }
    if len(rows) != 300 or len(seen) != 300:
        raise AlphaContractError("P026 no source-selected issuer may disappear")
    all_industries = sorted({
        sector for group in counts.values() for sector in group
    })
    overlaps = [
        {
            "industry": industry,
            "selected_exact": counts["SELECTED"][industry],
            "one_lane_exact": counts["ONE_LANE"][industry],
            "zero_lane_exact": counts["ZERO_LANE"][industry],
            "maximum_complete_industry_triplets_without_replacement": min(
                counts["SELECTED"][industry],
                counts["ONE_LANE"][industry],
                counts["ZERO_LANE"][industry],
            ),
        }
        for industry in all_industries
    ]
    maximum = sum(
        item["maximum_complete_industry_triplets_without_replacement"]
        for item in overlaps
    )
    matched_total = sum(x["exact_source_matches"] for x in by_arm.values())
    coverage = matched_total / 300
    gate_95 = coverage >= REQUIRED_SOURCE_COVERAGE_FRACTION
    gate_90 = all(
        x["source_match_fraction"] >= REQUIRED_PER_ARM_COVERAGE_FRACTION
        for x in by_arm.values()
    )
    result = {
        "schema_version": 1,
        "report_id": REPORT_ID,
        "analysis_date": "2026-10-21",
        "source_original_NSE_report_date": SECTOR_SOURCE_DATE,
        "source_original_index_member_count": 755,
        "source_original_exact_EQ_row_count": 744,
        "source_original_NSE_csv_sha256": SOURCE_SHA256,
        "source_original_NSE_git_blob_sha": SOURCE_BLOB_SHA,
        "selected_cohort_sha256": HG009_SELECTED_SHA,
        "matched_controls_sha256": HG009_CONTROL_SHA,
        "original_first_entry_session": FROZEN_ENTRY,
        "source_report_session_is_after_original_entry": (
            SECTOR_SOURCE_DATE > FROZEN_ENTRY
        ),
        "original_source_actual_first_retrieval_timestamp_verified_here": False,
        "source_category": "NIFTY_TOTAL_MARKET_CONSTITUENTS_NOT_FULL_NSE",
        "frozen_300_company_identities_unchanged": True,
        "arm_observations": by_arm,
        "all_source_identity_rows": sorted(
            rows, key=lambda x: (x["arm"], x["symbol"], x["frozen_isin"])
        ),
        "frozen_300_total": 300,
        "source_exact_match_count": matched_total,
        "source_exact_nonmatch_count": 300 - matched_total,
        "source_exact_match_fraction": round(coverage, 6),
        "sector_triplet_upper_bound_complete_count": maximum,
        "industry_strata_overlap": overlaps,
        "source_95pct_total_coverage_gate": gate_95,
        "source_90pct_each_arm_coverage_gate": gate_90,
        "original_oct15_preentry_source_gate": False,
        "sector_size_risk_conditioned_model_admissible": False,
        "sector_matched_three_arm_causal_inference_available": False,
        "size_float_exposure_source_independently_complete": False,
        "credit_regime_split_source_independently_complete": False,
        "future_cohort_must_use_independent_preentry_sector_size_source": True,
        "posthoc_source_reconstruction_must_not_change_h1_h5": True,
        "outcome_prices_or_share_returns_read_by_this_method": False,
        "stock_pick_model_trained_on_market_outcomes": False,
        "industry_membership_imputed_for_missing_issuers": False,
        "expected_return_forecast_produced": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def materialize(root: Path) -> dict[str, Any]:
    router, selected = load_hg009_inputs(root)
    controls = json.loads((
        root / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    return build_sector_identifiability_report(
        source_csv=(root / SOURCE_PATH).read_bytes(),
        router=router,
        selected=selected,
        controls=controls,
    )


def validate_report(packet: dict[str, Any], root: Path) -> None:
    unsigned = dict(packet)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P026 sealed source-coverage report tampered")
    if packet != materialize(root):
        raise AlphaContractError("P026 sector-source coverage not reproducible")
