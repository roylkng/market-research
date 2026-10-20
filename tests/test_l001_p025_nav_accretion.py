"""P025 original issuer HTML: date, price and certified-capital falsification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.l001_p025_nav_accretion import (
    _original_table,
    build_cash_nav_sensitivity,
    pinned_prior_sources,
    signed_capture,
    validate_capture,
    validate_cash_nav_result,
)
from scripts.archive_l001_p025_nav_accretion import run

ROOT = Path(__file__).resolve().parents[1]
# Original observed company daily count/rounded price excerpts. Test HTML is a
# SYNTHETIC fixture and is NEVER published as captured original issuer evidence.
SEP = [
    ("04",133517,"1360.99"),("07",265000,"1371.67"),
    ("08",92111,"1379.97"),("09",143401,"1391.49"),
    ("10",175000,"1400.72"),("11",184628,"1400.42"),
    ("15",242000,"1400.07"),("16",10000,"1389.17"),
    ("17",70100,"1417.56"),("18",104658,"1426.07"),
    ("21",35000,"1476.93"),("22",222000,"1472.58"),
    ("23",42000,"1477.40"),("24",60914,"1482.74"),
    ("25",21293,"1484.74"),("28",55522,"1529.78"),
    ("29",1797,"1530.00"),("30",0,None),
]
OCT = [
    ("01",144121,"1528.62"),("05",0,None),
    ("06",60892,"1529.86"),("07",0,None),
    ("08",95930,"1529.61"),("09",19403,"1530.00"),
    ("12",81571,"1530.00"),("13",261414,"1514.23"),
    ("14",3388,"1530.00"),("15",183000,"1526.10"),
    ("16",193000,"1496.31"),("19",194000,"1516.74"),
]


def _html() -> bytes:
    lines = [
        "<html><body><h1>The Great Eastern Shipping Company</h1>",
        "<h2>BUY BACK 2026</h2><h3>Daily Activity</h3>",
        ("<table><tr><th>Date</th><th>No. of Equity shares bought back</th>"
         "<th>Average Acquisition Price (INR/share)</th>"
         "<th>Cumulative Total No. of Equity Shares bought back</th></tr>"),
    ]
    cum = 0
    for month, entries in (("Sep", SEP), ("Oct", OCT)):
        for day, quantity, avg in entries:
            cum += quantity
            cells = [
                f"{day} {month} 2026",
                f"{quantity:,}" if quantity else "",
                avg or "",
                f"{cum:,}",
            ]
            lines.append("<tr>"+"".join(f"<td>{c}</td>" for c in cells)+"</tr>")
    lines += ["</table><p>*Excluding transaction and brokerage charges</p></body></html>"]
    return "".join(lines).encode("utf-8")


def test_exact_issuer_rows_preserve_original_cumulative_legal_timing():
    rows = _original_table(_html())
    assert len(rows) == 30
    assert rows[17]["date"] == "2026-09-30"
    assert rows[17]["issuer_cumulative_purchased"] == 1_858_941
    assert rows[-1]["issuer_cumulative_purchased"] == 3_095_660
    assert rows[-1]["issuer_rounded_avg_inr_per_share"] == "1516.74"


def test_sept_oct_cash_spend_and_cancellation_correctly_net_each_other():
    original = _html()
    receipt = signed_capture(
        original, observed_at_utc="2026-10-21T00:01:00+00:00"
    )
    validate_capture(receipt, original)
    prior, refs = pinned_prior_sources(ROOT)
    report = build_cash_nav_sensitivity(original, receipt, prior, refs)
    validate_cash_nav_result(
        report, raw=original, receipt=receipt, prior=prior, references=refs
    )
    assert report["sep_buyback_rounded_daily_purchased_shares"] == 1_858_941
    assert report["sep_estimated_cash_spend_cr_excluding_fees"] == 262.714746
    assert report["oct_to_19th_rounded_daily_purchased_shares"] == 1_236_719
    assert report["oct_to_19th_estimated_cash_spend_cr_excluding_fees"] == 187.802444
    assert report["cumulative_estimated_cash_spend_cr_excluding_fees"] == 450.517189
    ref = report["only_counterfactual_const_NAV_no_other_cash_change"]
    assert ref["sep_only_if_all_first_lot_legally_cancelled_inr"] == 1892.236792
    assert ref["sept_increment_inr_per_share_not_observed"] == 6.236792
    assert ref["if_oct_extra_also_legally_cancelled_inr"] == 1895.545561
    assert ref["full_sep_oct_increment_inr_per_share_not_observed"] == 9.545561
    assert ref["full_sep_oct_increment_percent_not_return"] == .506127
    assert report["investment_expected_return"] is None
    assert report["current_equity_margin_of_safety_verified"] is False
    assert report["live_capital_allowed"] is False


def test_forged_daily_cumulative_table_or_silent_new_oct21_row_rejected():
    wrong = _html().replace(b"30,95,660", b"31,95,660", 1)
    with pytest.raises(AlphaContractError, match="daily and cumulative"):
        _original_table(wrong)
    newer = _html().replace(
        b"</table>", b"<tr><td>20 Oct 2026</td><td></td>"
        b"<td></td><td>30,95,660</td></tr></table>",
    )
    with pytest.raises(AlphaContractError, match="30-day freeze"):
        _original_table(newer)


def test_receipt_tamper_or_capture_before_publication_is_rejected():
    original = _html()
    receipt = signed_capture(
        original, observed_at_utc="2026-10-21T00:01:00Z"
    )
    receipt["source_sha256"] = "f" * 64
    with pytest.raises(AlphaContractError, match="source receipt hash"):
        validate_capture(receipt, original)
    with pytest.raises(AlphaContractError, match="first-see"):
        signed_capture(original, observed_at_utc="2026-10-18T12:00:00Z")


def test_original_prior_share_source_tamper_rejected_by_sha():
    raw = _html()
    receipt = signed_capture(raw, observed_at_utc="2026-10-21T00:01:00Z")
    previous, refs = pinned_prior_sources(ROOT)
    previous["capital_bridge"]["certified_september_shares_extinguished"] = 55
    with pytest.raises(AlphaContractError, match="reference certified share"):
        build_cash_nav_sensitivity(raw, receipt, previous, refs)


def test_archive_script_publishes_only_original_content_addressed_bytes(
    tmp_path: Path,
):
    # Prior authentic original P023/P024 canonical source files are copied
    # *only* as test dependencies; synthetic HTML stays within tmp_path.
    from marketlab.l001_p025_nav_accretion import PINS
    for path, *_ in PINS.values():
        original = ROOT / path
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
    raw = _html()
    date = datetime(2026, 10, 21, tzinfo=UTC)
    response = run(
        tmp_path, run_id="synthetic-test",
        fetch=lambda url: (200, raw), now=lambda: date,
    )
    assert response["state"] == (
        "SIGNED_ORIGINAL_ISSUER_CASH_NAV_COUNTERFACTUAL_ARCHIVED"
    )
    assert run(
        tmp_path, run_id="synthetic-test",
        fetch=lambda url: (403, None), now=lambda: date,
    )["state"] == "ORIGINAL_ISSUER_BUYBACK_HTML_ALREADY_VERIFIED"
    packet = json.loads(
        (tmp_path / "research/l001/l001-p025-geship-issuer-buyback-cash-nav-v1.json")
        .read_text("utf-8")
    )
    assert packet["sep_estimated_cash_spend_cr_excluding_fees"] == 262.714746
    assert packet["live_capital_allowed"] is False


def test_failed_http_does_not_fabricate_nav_or_source(tmp_path: Path):
    response = run(
        tmp_path, run_id="source403",
        fetch=lambda url: (403, None),
        now=lambda: datetime(2026, 10, 21, tzinfo=UTC),
    )
    assert response["state"] == "BLOCKED_ISSUER_SOURCE_HTTP"
    assert response["report_created"] is False
    attempts = list(
        (tmp_path / "research/l001/originals/geship_2026_buyback_table/attempts")
        .glob("*.json")
    )
    assert len(attempts) == 1
    assert not (tmp_path /
        "research/l001/l001-p025-geship-issuer-buyback-cash-nav-v1.json"
    ).exists()
