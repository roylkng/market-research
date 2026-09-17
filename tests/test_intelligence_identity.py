from __future__ import annotations

import csv
import io
import zipfile
from datetime import date

from marketlab.intelligence_identity import identity_members_from_udiff
from marketlab.intelligence_news import entity_mentions

SESSION = date(2026, 9, 17)


def archive():
    fields = [
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "ISIN", "TckrSymb", "SctySrs",
        "FinInstrmNm", "OpnPric", "ClsPric", "PrvsClsgPric", "TtlTradgVol", "TtlTrfVal",
    ]
    rows = [
        ("TATACHEM", "INE092A01019", "TATA CHEMICALS LTD"),
        ("TATAINVEST", "INE672A01026", "TATA INVESTMENT CORP LTD"),
        ("NIACL", "INE470Y01017", "THE NEW INDIA ASSU CO LTD"),
        ("HDFCLIFE", "INE795G01014", "HDFC LIFE INS CO LTD"),
        ("SYRMA", "INE0DYJ01015", "SYRMA SGS TECHNOLOGY LTD"),
        ("MONQ50", "INF247L01AU3", "MOTILAL OSWAL NASDAQ Q50"),
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for symbol, isin, name in rows:
        writer.writerow({"TradDt": SESSION.isoformat(), "Sgmt": "CM", "Src": "NSE",
                         "FinInstrmTp": "STK", "ISIN": isin, "TckrSymb": symbol,
                         "SctySrs": "EQ", "FinInstrmNm": name, "OpnPric": 100,
                         "ClsPric": 100, "PrvsClsgPric": 100, "TtlTradgVol": 1,
                         "TtlTrfVal": 100})
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zipped:
        zipped.writestr("bhav.csv", out.getvalue())
    return payload.getvalue()


def members():
    return identity_members_from_udiff(archive(), session_date=SESSION, deep_members=[])


def test_prior_nse_identity_expands_beyond_deep_panel():
    symbols = {row["symbol"] for row in members()}
    assert {"TATACHEM", "TATAINVEST", "NIACL", "HDFCLIFE", "SYRMA"} <= symbols
    assert "MONQ50" not in symbols


def test_deterministic_aliases_recover_common_exchange_abbreviations():
    resolved = members()
    assert entity_mentions("New India Assurance shares rise", resolved)["panel_symbols"] == ["NIACL"]
    assert entity_mentions("HDFC Life gains on insurance changes", resolved)["panel_symbols"] == ["HDFCLIFE"]
    assert entity_mentions("Tata Investment Corporation is in focus", resolved)["panel_symbols"] == ["TATAINVEST"]
    assert entity_mentions("Tata Chemicals gains", resolved)["panel_symbols"] == ["TATACHEM"]
    assert entity_mentions("Syrma SGS Technology shares jump", resolved)["panel_symbols"] == ["SYRMA"]


def test_unrelated_tata_story_does_not_link_group_companies_by_name_alone():
    resolved = members()
    found = entity_mentions("Tata Sons board meeting concludes", resolved)["panel_symbols"]
    assert "TATACHEM" not in found
    assert "TATAINVEST" not in found
