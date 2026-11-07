from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_context import (
    build_card,
    discover_history,
    parse_actions,
    parse_quote,
    render_report,
    retain_json,
    select_period,
    source_time,
    year_ago,
)
from marketlab.company_change_store import EvidenceStore

IDENTITY = {"symbol": "TEST", "isin": "INE000A01001", "scope": "CONSOLIDATED"}
NOW = "2026-11-07T12:00:00+00:00"


def period(start, end, revenue, pat, *, eps=None, published="2026-11-06T10:00:00+00:00"):
    facts = {"revenue": {"value": revenue, "unit": "INR_crore"},
             "group_pat": {"value": pat, "unit": "INR_crore"},
             "owner_pat": {"value": pat - 1, "unit": "INR_crore"},
             "cfo": {"value": pat * 1.1, "unit": "INR_crore"}}
    if eps is not None:
        facts["diluted_eps"] = {"value": eps, "unit": "INR_per_share"}
    return {"period_start": start, "period_end": end, "facts": facts,
            "identity": dict(IDENTITY), "source_url": "https://nsearchives.nseindia.com/source.xml",
            "raw_sha256": canonical_hash([start, end]), "known_at": NOW, "published_at": published}


def evidence():
    return [period("2025-04-01", "2026-03-31", 100, 10, eps=5),
            period("2026-04-01", "2026-09-30", 60, 6),
            period("2025-04-01", "2025-09-30", 40, 4)]


def quote_payload():
    return {"info": {"symbol": "TEST", "isin": "INE000A01001"},
            "metadata": {"isin": "INE000A01001", "series": "EQ", "lastUpdateTime": "06-Nov-2026 15:30:00"},
            "priceInfo": {"lastPrice": 70, "close": 71}}


def quote():
    return parse_quote(quote_payload(), IDENTITY, NOW)


def actions():
    return parse_actions([], "TEST", "2025-03-31", "2026-11-07")


def card(data=None, q=None, a=None):
    return build_card(IDENTITY, data or evidence(), "2026-09-30", q or quote(), a or actions(), NOW)


def test_exact_year_ago_ttm_and_reverse_hurdle():
    result = card()
    current = result["year_ago_comparisons"][0]
    assert current["metrics"]["revenue"]["reported_growth_fraction"] == .5
    assert current["basis"].startswith("CROSS_SOURCE")
    ttm = result["reported_ttm_flows"]
    assert ttm["fields"]["revenue"]["value"] == 120
    assert ttm["fields"]["owner_pat"]["value"] == 11
    assert "diluted_eps" not in ttm["fields"]
    assert "shares" not in ttm["fields"]
    assert result["price_over_reported_annual_eps"] == 14
    assert result["reverse_hurdle_scenarios"][1]["required_annual_eps_growth"] == pytest.approx((14 * 1.15**5 / 15)**.2 - 1)
    assert result["disposition"] == "RESEARCH_CONTEXT_NOT_BUY_APPROVAL"
    assert result["live_capital_allowed"] is False


def test_current_price_is_last_trade_not_assumed_official_close():
    q = quote()
    assert q["price"] == 70
    assert q["price_type"] == "LAST_TRADED_OBSERVATION_NOT_EXECUTABLE_CLOSE"
    assert q["quoted_at"].endswith("+05:30")
    assert not q["stale"]


@pytest.mark.parametrize("bad", [0, -1, True, "70", float("nan"), float("inf")])
def test_invalid_price_never_used(bad):
    p = quote_payload()
    p["priceInfo"]["lastPrice"] = bad
    with pytest.raises(ChangeError):
        parse_quote(p, IDENTITY, NOW)


@pytest.mark.parametrize("fault", ["symbol", "isin", "series", "future", "timestamp"])
def test_quote_identity_and_timestamp_gates(fault):
    p = quote_payload()
    if fault == "symbol":
        p["info"]["symbol"] = "OTHER"
    elif fault == "isin":
        p["metadata"]["isin"] = "INE000A01002"
    elif fault == "series":
        p["metadata"]["series"] = "BE"
    elif fault == "future":
        p["metadata"]["lastUpdateTime"] = "08-Nov-2026 15:30:00"
    else:
        p["metadata"].pop("lastUpdateTime")
    with pytest.raises(ChangeError):
        parse_quote(p, IDENTITY, NOW)


def test_stale_quote_withholds_hurdle_not_just_a_footnote():
    q = quote()
    q["quoted_at"] = "2026-10-01T10:00:00+00:00"
    r = card(q=q)
    assert r["price_over_reported_annual_eps"] is None
    assert r["reverse_hurdle_scenarios"] == []


@pytest.mark.parametrize("subject", ["Bonus 1:1", "Face Value Split", "Rights Issue", "Scheme of Arrangement", "Unknown purpose", "Dividend and Bonus"])
def test_share_basis_changes_block_ratios(subject):
    a = parse_actions([{"symbol": "TEST", "exDate": "01-Jun-2026", "subject": subject}],
                      "TEST", "2026-03-31", "2026-11-07")
    result = card(a=a)
    assert result["price_over_reported_annual_eps"] is None
    assert result["reverse_hurdle_scenarios"] == []
    assert "reconciliation" in result["blockers"][-1]


def test_dividend_does_not_change_eps_basis_but_is_not_added_to_returns():
    a = parse_actions([{"symbol": "TEST", "exDate": "01-Jun-2026", "subject": "Dividend - Rs 5 Per Share"}],
                      "TEST", "2026-03-31", "2026-11-07")
    assert not a["share_basis_changes_or_unknown_actions"]
    assert card(a=a)["price_over_reported_annual_eps"] == 14
    assert any("omit dividends" in s for s in card(a=a)["limitations"])


def test_incomplete_action_date_window_does_not_pass():
    a = actions()
    a["start_exclusive"] = "2026-06-01"
    assert card(a=a)["price_over_reported_annual_eps"] is None


def test_missing_actions_or_quote_do_not_generate_scenarios():
    for q, a in ((None, actions()), (quote(), None)):
        r = build_card(IDENTITY, evidence(), "2026-09-30", q, a, NOW)
        assert not r["reverse_hurdle_scenarios"]


def test_cross_scope_and_future_inputs_rejected():
    for field, value in (("known_at", "2027-01-01T00:00:00Z"), ("published_at", "2027-01-01T00:00:00Z")):
        data = evidence()
        data[0][field] = value
        with pytest.raises(ChangeError, match="cutoff"):
            card(data=data)
    data = evidence()
    data[0]["identity"]["scope"] = "STANDALONE"
    with pytest.raises(ChangeError, match="scope"):
        card(data=data)


def test_missing_prior_period_is_not_zero_or_annualized():
    data = evidence()[:2]
    r = card(data=data)
    assert r["reported_ttm_flows"] is None
    assert r["year_ago_comparisons"][0]["metrics"]["revenue"]["previous"] is None
    r = card(data=evidence()[1:])
    assert r["reported_annual_diluted_eps"] is None
    assert r["price_over_reported_annual_eps"] is None


def test_missing_cash_value_stays_missing_in_ttm():
    data = evidence()
    del data[1]["facts"]["cfo"]
    result = card(data=data)
    assert result["reported_ttm_flows"]["fields"]["cfo"]["value"] is None
    assert result["reported_ttm_flows"]["fields"]["revenue"]["value"] == 120


def test_nonpositive_prior_profit_has_no_growth_percentage():
    for previous in (0, -10):
        data = evidence()
        data[2]["facts"]["group_pat"]["value"] = previous
        result = card(data=data)
        assert result["year_ago_comparisons"][0]["metrics"]["group_pat"]["reported_growth_fraction"] is None


def test_latest_published_restatement_wins_not_later_observation():
    old = evidence()[0]
    new = copy.deepcopy(old)
    old["known_at"] = "2026-11-07T12:00:00Z"
    new["known_at"] = "2026-11-07T11:00:00Z"
    new["published_at"] = "2026-11-07T10:00:00Z"
    new["facts"]["revenue"]["value"] = 110
    assert select_period([old, new], old["period_start"], old["period_end"])["facts"]["revenue"]["value"] == 110


def test_same_publication_conflict_is_not_first_value_wins():
    old = evidence()[0]
    conflicting = copy.deepcopy(old)
    conflicting["facts"]["revenue"]["value"] = 999
    with pytest.raises(ChangeError, match="conflicting"):
        select_period([old, conflicting], old["period_start"], old["period_end"])


def test_bad_units_not_silently_scaled():
    data = evidence()
    data[0]["facts"]["diluted_eps"]["unit"] = "INR_crore"
    with pytest.raises(ChangeError, match="unit"):
        card(data=data)


def test_leap_day_and_timezone_dates():
    assert year_ago("2024-02-29") == "2023-02-28"
    assert source_time("06-Nov-2026 15:30:00").astimezone(ZoneInfo("UTC")).hour == 10


def test_source_payload_hash_not_reconstructed_values(tmp_path):
    raw = b'{"data": [1,2]}'
    with EvidenceStore(tmp_path) as store:
        c = retain_json(store, {"data": [1, 2]}, raw, "https://nseindia.com/api/test")
        assert c["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert store.read_blob(c["raw_sha256"]) == raw
        with pytest.raises(ChangeError, match="bytes"):
            retain_json(store, {"data": [2, 3]}, raw, "https://nseindia.com/api/test")


class HistoryClient:
    INTEGRATED_FILING_ENDPOINT = SimpleNamespace(url="https://www.nseindia.com/api/integrated-filing-results")

    def __init__(self, repeat=False):
        self.calls = []
        self.repeat = repeat

    def _json_get_with_raw(self, endpoint, *, params):
        self.calls.append(params)
        page = 1 if self.repeat else params["page"]
        source = {"symbol": "TEST", "consolidated": "Consolidated", "qe_Date": "31-Mar-2026",
                  "broadcast_Date": "01-May-2026 12:00:00",
                  "xbrl": f"https://nsearchives.nseindia.com/{page}.xml"}
        payload = {"data": [source], "totalCount": 2}
        return payload, json.dumps(payload).encode()


def test_historical_pagination_does_not_assume_200_rows_arrived(tmp_path):
    client = HistoryClient()
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store:
        sources, receipts = discover_history(client, store, IDENTITY, "2026-09-30")
    assert len(client.calls) == 2
    assert len(receipts) == 2
    assert len(sources) == 1  # latest source per end date
    assert all(c["symbol"] == "TEST" for c in client.calls)


def test_repeated_historical_page_fails_coverage(tmp_path):
    with EvidenceStore(tmp_path, clock=lambda: NOW) as store, pytest.raises(ChangeError, match="repeated"):
        discover_history(HistoryClient(repeat=True), store, IDENTITY, "2026-09-30")


def test_report_escapes_source_content_and_is_deterministic():
    original = evidence()
    before = copy.deepcopy(original)
    c = card(original)
    assert original == before
    assert c == card(original)
    c["identity"] = {**IDENTITY, "symbol": "<script>bad</script>"}
    c["retrieval_errors"] = []
    text = render_report({"cards": [c], "as_of": NOW})
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "No forecast" in text
