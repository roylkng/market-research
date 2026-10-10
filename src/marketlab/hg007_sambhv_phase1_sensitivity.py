"""SAMBHV original-source Phase-I steel/captive-power conditional CAPEX.

Never alter HG005-D003's frozen mechanical payoff sensitivity. This
adds a second mutually exclusive boundary case *if* the listed 25 MW
power plant is needed for the steel EBITDA-per-ton assumptions. No
future earnings, financing, cost of capital, current FD shares or
investment recommendation is inferred.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

ORIGINAL_URL = (
    "https://www.sambhv.com/uploads/pdf/investors/"
    "financial-performance/results/2026-2027/Investor-Presentation.pdf"
)

MODEL_ID = "HG007-P017-SAMBHV-STEEL-POWER-PHASE1-BOUNDARY-v1"
SOURCES = {
    "SAMBHV_P016_RECEIPT": (
        "research/hg007/sambhv-aug2026-investor/source-receipt-v1.json",
        "afd1f55dec53bb5482e63dcb19bf83ecbdc28fe0",
    ),
    "HG005_MARKET_REFERENCE": (
        "research/hg005-d001-result-v1.json",
        "2dbbc3055d1aacec8a37dd510a1a75a3c7868006",
    ),
    "HG005_ORIGINAL_HURDLES": (
        "research/hg005-d003-result-v1.json",
        "b235bd9168bc658f7511f9cec1913f20f82cf311",
    ),
}
PDF_SHA256 = "19e6f9faea1aaaec481ad3ab9c842a58b96bfae636f146143f44e3a42b6d696d"
PDF_PATH = (
    "research/hg007/sambhv-aug2026-investor/raw/sha256/"
    + PDF_SHA256
    + ".pdf"
)
INR_PER_CRORE = 10_000_000.0


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()


def _verify_original_page_9(raw: bytes) -> str:
    """Recheck original issuer roadmap page without importing the CLI script.

    This is supported by exact SHA-pinned original bytes and the P016
    43-page source receipt. Re-reading the page validates the source
    page-to-terms link, not the future economic dependency.
    """
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if len(reader.pages) != 43:
            raise ValueError("original source is not 43 PDF pages")
        text = reader.pages[8].extract_text() or ""
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("original Sambhv roadmap PDF page could not be verified") from exc
    page_sha = hashlib.sha256(text.encode()).hexdigest()
    if page_sha != "c57f4b31a8c55113312ab6658773071e53e2835b1e6d8ab4a1b8808b1af49197":
        raise ValueError("original issuer roadmap PDF page 9 text hash mismatch")
    folded = " ".join(text.casefold().split())
    for token in ("0.36", "8,100", "25 mw", "1,250", "q4fy27"):
        if token not in folded:
            raise ValueError("source Phase I roadmap lacks original steel/power token")
    return page_sha


def _pinned_json(root: Path, key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    relative, git_sha = SOURCES[key]
    original_bytes = (root / relative).read_bytes()
    if _git_blob_sha(original_bytes) != git_sha:
        raise ValueError(f"{key}: original pinned Git blob mismatch")
    data = json.loads(original_bytes)
    if not isinstance(data, dict):
        raise TypeError(f"{key}: original source must be JSON object")
    return data, {
        "path": relative,
        "git_blob_sha": git_sha,
        "raw_sha256": hashlib.sha256(original_bytes).hexdigest(),
    }


def load_sambhv_pinned_sources(root: Path) -> tuple[dict, dict, dict, dict]:
    receipt, receipt_ref = _pinned_json(root, "SAMBHV_P016_RECEIPT")
    market, market_ref = _pinned_json(root, "HG005_MARKET_REFERENCE")
    original, original_ref = _pinned_json(root, "HG005_ORIGINAL_HURDLES")
    raw = (root / PDF_PATH).read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != PDF_SHA256 or len(raw) != 5_654_565:
        raise ValueError("original Sambhv 43-page issuer PDF raw SHA/size changed")
    if (
        receipt.get("case_id") != "HG007-P016-SAMBHV-Q1FY27-ORIGINAL-PHASE1-CAPEX-v1"
        or receipt.get("status") != "ORIGINAL_ISSUER_PDF_BYTES_AND_ROADMAP_IDENTITY_VERIFIED"
        or receipt.get("raw_sha256") != PDF_SHA256
        or receipt.get("source_url") != ORIGINAL_URL
        or receipt.get("source_filing_date") != "2026-08-03"
        or receipt.get("steel_power_budget_aggregation_authorized") is not False
        or receipt.get("power_plant_is_economically_required_for_steel_ebitda_verified")
        is not None  # This field is inside the original document evidence.
    ):
        raise ValueError("Sambhv original P016 source/conditional boundary modified")
    _verify_original_page_9(raw)
    parsed_terms = receipt.get("document_identity_evidence")
    if not isinstance(parsed_terms, dict):
        raise TypeError("original issuer P016 document evidence is required")
    if (
        parsed_terms.get("roadmap_page_number") != 9
        or parsed_terms.get("source_declared_steel_capacity_mmtpa") != 0.36
        or parsed_terms.get("source_declared_steel_capex_inr_crore") != 810
        or parsed_terms.get("source_declared_power_capacity_mw") != 25
        or parsed_terms.get("source_declared_power_capex_inr_crore") != 125
        or parsed_terms.get("both_stated_target_commissioning") != "Q4FY27"
        or parsed_terms.get("power_plant_is_economically_required_for_steel_ebitda_verified")
        is not False
    ):
        raise ValueError("verified original steel or power source terms changed")
    provenance = {
        "source_receipt": receipt_ref,
        "original_hg005_market": market_ref,
        "original_hg005_hurdle": original_ref,
        "original_issuer_pdf": {
            "path": PDF_PATH,
            "sha256": PDF_SHA256,
            "byte_count": len(raw),
            "roadmap_page_number_one_based": 9,
            "roadmap_text_sha256": parsed_terms["roadmap_text_sha256"],
        },
    }
    return receipt, market, original, provenance


def _positive(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name}: expected finite positive source number")
    return float(value)


def build_steel_power_sensitivity(
    receipt: dict[str, Any],
    market: dict[str, Any],
    original: dict[str, Any],
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if (
        receipt.get("raw_sha256") != PDF_SHA256
        or receipt.get("document_identity_evidence", {}).get("roadmap_text_sha256")
        != "c57f4b31a8c55113312ab6658773071e53e2835b1e6d8ab4a1b8808b1af49197"
        or receipt.get("company_fcf_or_ebitda_uplift_verified") is not False
        or receipt.get("live_capital_allowed") is not False
    ):
        raise ValueError("not the source-verified original 43-page issuer roadmap")
    if (
        market.get("context_id") != "HG005-D001-v1"
        or market.get("price_session") != "2026-10-01"
        or market.get("live_capital_allowed") is not False
        or original.get("context_id") != "HG005-D003-v1"
        or original.get("completion_probabilities_assigned") is not False
        or original.get("expected_returns_calculated") is not False
        or original.get("live_capital_allowed") is not False
    ):
        raise ValueError("frozen HG005 original context or scientific state changed")
    context = market.get("key_mechanical_context", {}).get("SAMBHV")
    hurdle = original.get("key_hurdles", {}).get("SAMBHV")
    if not isinstance(context, dict) or not isinstance(hurdle, dict):
        raise TypeError("HG005 Sambhv capital reference/hurdle missing")
    capitalization = _positive(
        context.get("reported_fd_market_cap_inr_crore"),
        "frozen original Oct1 market capitalization",
    )
    if not math.isclose(capitalization, 4757.470221205, abs_tol=1e-8):
        raise ValueError("original 1 October Sambhv market reference changed")
    if context.get("close_price_inr") != 161.45:
        raise ValueError("original Sambhv market price session changed")
    capacity = _positive(hurdle.get("phase1_capacity_addition_mmtpa"), "Phase I MMTPA")
    steel_capex = _positive(hurdle.get("phase1_capex_inr_crore"), "steel CAPEX")
    power_capex = _positive(
        receipt["document_identity_evidence"]["source_declared_power_capex_inr_crore"],
        "separate captive power CAPEX",
    )
    if capacity != 0.36 or steel_capex != 810 or power_capex != 125:
        raise ValueError("steel/power Phase I source family changed")
    if original.get("key_hurdles", {}).get("SAMBHV", {}).get("state") != "SENSITIVITY_READY":
        raise ValueError("original sensitivity stage changed")

    rows = []
    for case_name, key in (
        ("ILLUSTRATIVE_STRONG", "illustrative_strong_cell"),
        ("ILLUSTRATIVE_MID", "illustrative_mid_cell"),
    ):
        saved = hurdle.get(key)
        if not isinstance(saved, dict):
            raise TypeError(f"HG005 {key} frozen surface missing")
        use = _positive(saved.get("utilization_pct"), "capacity use %")
        per_tonne = _positive(saved.get("ebitda_per_tonne_inr"), "EBITDA / tonne")
        multiple = _positive(saved.get("ev_ebitda_multiple"), "illustrative EV/EBITDA")
        if use > 100:
            raise ValueError("capacity utilization above 100 percent")
        tonnes = capacity * 1_000_000 * use / 100.0
        hypothetical_ebitda = tonnes * per_tonne / INR_PER_CRORE
        gross_value = hypothetical_ebitda * multiple
        after_steel = gross_value - steel_capex
        after_both = gross_value - steel_capex - power_capex
        if not math.isclose(
            after_steel / capitalization,
            saved.get("conservative_net_equity_value_to_market_cap"),
            abs_tol=1e-10,
        ):
            raise ValueError(f"{case_name}: source HG005 original mechanical payoff drifted")
        rows.append({
            "original_cell": case_name,
            "hypothetical_capacity_utilization_pct": use,
            "hypothetical_ebitda_per_tonne_inr": per_tonne,
            "hypothetical_ev_to_ebitda_multiple": multiple,
            "implied_operating_tonnes_per_year": tonnes,
            "illustrative_annual_operating_ebitda_inr_crore": hypothetical_ebitda,
            "hypothetical_gross_incremental_ev_inr_crore": gross_value,
            "steel_only_original_capex_inr_crore": steel_capex,
            "steel_plus_power_conditional_capex_inr_crore": steel_capex + power_capex,
            "original_steel_only_net_increment_inr_crore": after_steel,
            "conditional_steel_plus_power_net_increment_inr_crore": after_both,
            "original_steel_only_net_increment_to_frozen_cap": after_steel / capitalization,
            "conditional_steel_plus_power_net_increment_to_frozen_cap": (
                after_both / capitalization
            ),
            "change_due_only_to_extra_power_capex_fraction_of_frozen_cap": (
                -power_capex / capitalization
            ),
            "independent_power_only_ebitda_required_to_offset_capex_at_same_multiple_cr": (
                power_capex / multiple
            ),
            "power_ebitda_savings_separately_verified": False,
            "project_expected_stock_return": None,
        })
    return {
        "schema_version": 1,
        "sensitivity_id": MODEL_ID,
        "classification": "SOURCE_VERIFIED_CAPEX_BOUNDARY_DIAGNOSTIC_NOT_EXPECTED_RETURN",
        "issuer": "Sambhv Steel Tubes Limited",
        "symbol": "SAMBHV",
        "as_of_issuer_presentation": "2026-08-03",
        "historical_unchanged_market_price_date": "2026-10-01",
        "historical_unchanged_market_price_inr": 161.45,
        "historical_reported_fd_market_cap_inr_crore": capitalization,
        "source_provenance": provenance,
        "source_verified_steel_coils_capacity_add_mmtpa": capacity,
        "source_verified_steel_only_capex_inr_crore": steel_capex,
        "source_verified_separate_captive_power_mw": 25,
        "source_verified_additional_power_capex_inr_crore": power_capex,
        "source_target_steel_and_power_commissioning": "Q4FY27",
        "two_alternative_assumptions_not_additive_payoff_estimates": rows,
        "source_lists_other_project_spend_not_included": {
            "sarora_30mw_power_inr_crore": 150,
            "kuthrel_8mw_rooftop_solar_inr_crore": 25,
            "erw_0_15mmtpa_brownfield_inr_crore": 50,
        },
        "power_plant_required_for_assumed_steel_ebitda_verified": False,
        "incremental_power_capex_fully_funded_or_spent_verified": False,
        "new_plant_operational_ebitda_verified": False,
        "future_steel_power_synergy_ebitda_verified": False,
        "original_hg005_hurdle_modified": False,
        "company_probability_or_alpha_computed": False,
        "stock_price_target_or_future_return_computed": False,
        "independently_current_fd_shares_verified": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
