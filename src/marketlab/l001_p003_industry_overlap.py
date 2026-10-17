"""L001 P003: outcome-blind exact NSE Total Market industry source overlap.

D015/SC002 source readiness is separately frozen. A row existing in a CSV
does NOT mean SC002 has a READY-before-cutoff industry snapshot. No industrial
or finance model is authorized by this diagnostic.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from hashlib import sha256

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p002_intake import COHORT_SHA256

SOURCE_SHA256 = "692caee1b8e4fd11912c71e1c2519c4070e9675f9a0a9e6d40294cdf032890fc"
READINESS_SHA256 = "955699a9f6361083c9ed97d806800e518c1ccaf404700f5d638d5b838ed9cb87"
COLUMNS = ("Company Name", "Industry", "Symbol", "Series", "ISIN Code")


def build_provisional_industry_crosswalk(
    cohort: dict, original_csv: bytes, pinned_readiness: dict,
) -> dict:
    if not isinstance(original_csv, bytes) or sha256(original_csv).hexdigest() != SOURCE_SHA256:
        raise AlphaContractError("original NSE CSV bytes do not match frozen content hash")
    unsigned_cohort = {k: v for k, v in cohort.items() if k != "cohort_sha256"}
    if cohort.get("cohort_sha256") != COHORT_SHA256 or digest(unsigned_cohort) != COHORT_SHA256:
        raise AlphaContractError("HG009 original 100-name cohort hash changed")
    unsigned_readiness = {k: v for k, v in pinned_readiness.items() if k != "summary_sha256"}
    if (
        pinned_readiness.get("summary_sha256") != READINESS_SHA256
        or digest(unsigned_readiness) != READINESS_SHA256
        or pinned_readiness.get("analysis_id") != "RM001-SC002-INDUSTRY-READINESS-v1"
        or pinned_readiness.get("ready_before_cutoff_session_count") != 0
        or pinned_readiness.get("prospective_industry_source_ready") is not False
    ):
        raise AlphaContractError("SC002 archived readiness boundary altered")
    try:
        contents = original_csv.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AlphaContractError("original NSE CSV encoding invalid") from exc
    reader = csv.DictReader(io.StringIO(contents, newline=""))
    if reader.fieldnames != list(COLUMNS):
        raise AlphaContractError("NSE official industry header changed")
    exact = {}
    all_rows = 0
    for row in reader:
        all_rows += 1
        symbol = (row.get("Symbol") or "").strip().upper()
        isin = (row.get("ISIN Code") or "").strip().upper()
        industry = (row.get("Industry") or "").strip()
        series = (row.get("Series") or "").strip().upper()
        if not symbol or len(isin) != 12 or not industry or not row.get("Company Name"):
            raise AlphaContractError("NSE official classification row incomplete")
        if series == "EQ":
            key = (symbol, isin)
            if key in exact:
                raise AlphaContractError("duplicate NSE EQ classification identity")
            exact[key] = industry
    if all_rows < 700 or len(exact) < 700:
        raise AlphaContractError("NSE Total Market source census incomplete")
    members = cohort.get("selected")
    if not isinstance(members, list) or len(members) != 100:
        raise AlphaContractError("HG009 100-member roster incomplete")
    rows = []
    ids = set()
    for source in members:
        symbol, isin = source.get("symbol"), source.get("isin")
        key = (symbol, isin)
        if key in ids or not isinstance(symbol, str) or not isinstance(isin, str):
            raise AlphaContractError("HG009 issuer identity collision")
        ids.add(key)
        match = exact.get(key)
        rows.append({
            "symbol": symbol, "isin": isin,
            "provisional_industry_from_exact_csv": match,
            "source_evidence": (
                "EXACT_SYMBOL_ISIN_NSE_CSV_OBSERVATION_NON_ADMISSIBLE"
                if match is not None else "NO_EXACT_MATCH_IN_INDEX_SUBSET"
            ),
            "potential_financial_services_not_valuation_class": (
                match == "Financial Services"
            ),
            "industry_model_admitted": False,
            "valuation_ready": False,
            "investment_authorized": False,
        })
    rows.sort(key=lambda r: (r["symbol"], r["isin"]))
    financials = [r["symbol"] for r in rows if r["potential_financial_services_not_valuation_class"]]
    report = {
        "schema_version": 1,
        "review_id": "L001-P003-20261017-EXACT-CLASSIFICATION-SOURCE-OVERLAP-v1",
        "original_frozen_cohort_sha256": COHORT_SHA256,
        "original_nse_csv_sha256": SOURCE_SHA256,
        "original_source_session": "2026-10-16",
        "pinned_sc002_readiness_sha256": READINESS_SHA256,
        "sc002_ready_before_cutoff_sessions": 0,
        "source_is_quality_approved_for_model": False,
        "csv_row_count": all_rows,
        "original_frozen_cohort_count": len(rows),
        "exact_identity_matches": len(rows) - sum(
            r["provisional_industry_from_exact_csv"] is None for r in rows
        ),
        "outside_nifty_total_market_subset": sum(
            r["provisional_industry_from_exact_csv"] is None for r in rows
        ),
        "financial_services_caution_symbols": financials,
        "provisional_industry_counts": dict(sorted(Counter(
            r["provisional_industry_from_exact_csv"]
            for r in rows if r["provisional_industry_from_exact_csv"] is not None
        ).items())),
        "rows": rows,
        "no_historical_classification_backfill": True,
        "all_economic_valuations_still_blocked": True,
        "predicted_return": None,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
