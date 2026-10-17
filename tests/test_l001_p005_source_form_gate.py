"""L001 P005 never mistakes generic accounting forms for industrial proof."""

from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p005_source_form_gate import (
    classify_financial_reporting_scope,
    original_filing_format,
)


def test_original_nse_financial_accounting_format_is_a_specialist_gate():
    url = (
        "https://nsearchives.nseindia.com/corporate/xbrl/"
        "INTEGRATED_FILING_NBFC_INDAS_1661603_29042026054321_WEB.xml"
    )
    assert original_filing_format(url) == "NSE_NBFC_INDAS_FINANCIAL_ACCOUNTING_FORMAT"


def test_generic_indas_does_not_prove_industrial_sector():
    url = (
        "https://nsearchives.nseindia.com/corporate/xbrl/"
        "INTEGRATED_FILING_INDAS_1661603_29042026054321_WEB.xml"
    )
    assert original_filing_format(url) == "NSE_GENERAL_INDAS_ACCOUNTING_FORMAT"


@pytest.mark.parametrize("url", [
    "http://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_NBFC_INDAS_1_WEB.xml",
    "https://nsearchives.nseindia.com.evil.test/INTEGRATED_FILING_NBFC_INDAS_1_WEB.xml",
    "https://example.com/INTEGRATED_FILING_INDAS_1_WEB.xml",
    "not a URL", None,
])
def test_unverified_or_spoofed_filing_url_is_not_admitted(url):
    assert original_filing_format(url) == "UNVERIFIED_ORIGINAL_FORMAT"


def test_resealed_fake_original_report_does_not_bypass_pin():
    report = {
        "report_id": "L001-P004-FROZEN-HG009-ALL100-ORIGINAL-REPLAY-v1",
        "company_count": 100,
        "original_xml_sha256_checked": 300,
        "original_numeric_xbrl_values_replayed": 400,
        "live_capital_allowed": False,
        "source_results": [],
    }
    report["report_sha256"] = digest(report)
    with pytest.raises(AlphaContractError, match="original P004"):
        classify_financial_reporting_scope(report)
