"""L001 P005: original NSE financial-reporting-format gate, not industry inference.

NSE's NBFC-specific original financial form is evidence that industrial
CFO/PPE and ROIC screens are inappropriate. The generic INDAS form does not
prove a company is industrial, nor does it establish sector classification.
"""

from __future__ import annotations

from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest

P004_SHA256 = "97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d"
P004_ID = "L001-P004-FROZEN-HG009-ALL100-ORIGINAL-REPLAY-v1"


def original_filing_format(url: object) -> str:
    if not isinstance(url, str):
        return "UNVERIFIED_ORIGINAL_FORMAT"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "nsearchives.nseindia.com":
        return "UNVERIFIED_ORIGINAL_FORMAT"
    filename = parsed.path.rsplit("/", 1)[-1].upper()
    if not filename.endswith("_WEB.XML"):
        return "UNVERIFIED_ORIGINAL_FORMAT"
    if filename.startswith("INTEGRATED_FILING_NBFC_INDAS_"):
        return "NSE_NBFC_INDAS_FINANCIAL_ACCOUNTING_FORMAT"
    if filename.startswith("INTEGRATED_FILING_INDAS_"):
        return "NSE_GENERAL_INDAS_ACCOUNTING_FORMAT"
    return "UNVERIFIED_ORIGINAL_FORMAT"


def classify_financial_reporting_scope(p004: dict) -> dict:
    """Conservatively flag only the exact original financial accounting form."""
    unsigned = {key: value for key, value in p004.items() if key != "report_sha256"}
    if p004.get("report_sha256") != P004_SHA256 or digest(unsigned) != P004_SHA256:
        raise AlphaContractError("original P004 300-document source replay seal changed")
    if (
        p004.get("report_id") != P004_ID
        or p004.get("company_count") != 100
        or p004.get("original_xml_sha256_checked") != 300
        or p004.get("original_numeric_xbrl_values_replayed") != 400
        or p004.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("P004 original source replay integrity status changed")
    originals = p004.get("source_results")
    if not isinstance(originals, list) or len(originals) != 100:
        raise AlphaContractError("P004 exact 100-company panel unavailable")
    result = []
    for row in originals:
        sources = row.get("financial_sources", {})
        if not isinstance(sources, dict) or not all(
            isinstance(sources.get(key), dict) for key in ("annual", "quarter")
        ):
            raise AlphaContractError("issuer has no original annual/quarter source proof")
        annual = original_filing_format(sources["annual"].get("original_url"))
        quarter = original_filing_format(sources["quarter"].get("original_url"))
        if annual != quarter or annual == "UNVERIFIED_ORIGINAL_FORMAT":
            raise AlphaContractError("original cross-period XBRL filing format not comparable")
        financial_form = annual == "NSE_NBFC_INDAS_FINANCIAL_ACCOUNTING_FORMAT"
        result.append({
            "symbol": row["symbol"],
            "isin": row["isin"],
            "source_based_accounting_format": annual,
            "requires_financial_institution_specialist_review": financial_form,
            "industrial_roic_or_cfo_ppe_investment_rank_allowed": False,
            "official_industry_or_financial_licence_proved": False,
            "full_owner_cash_ready": False,
            "expected_return": None,
            "investment_authorized": False,
        })
    result.sort(key=lambda row: (row["symbol"], row["isin"]))
    pairs = [(row["symbol"], row["isin"]) for row in result]
    if len(set(pairs)) != 100:
        raise AlphaContractError("duplicate source issuer identity")
    flagged = [row["symbol"] for row in result
               if row["requires_financial_institution_specialist_review"]]
    report = {
        "schema_version": 1,
        "report_id": "L001-P005-SOURCE-FORM-GATE-v1",
        "source_original_replay_sha256": P004_SHA256,
        "cohort_count": 100,
        "nbfc_financial_accounting_forms": len(flagged),
        "nbfc_financial_accounting_form_symbols": flagged,
        "general_indas_forms_unclassified_industry": 100 - len(flagged),
        "official_industry_classification_proved": False,
        "sector_specific_owner_cash_ready": 0,
        "source_forms_from_original_verified_filings_only": True,
        "frozen_experiments_untouched": True,
        "live_capital_allowed": False,
        "companies": result,
    }
    report["report_sha256"] = digest(report)
    return report
