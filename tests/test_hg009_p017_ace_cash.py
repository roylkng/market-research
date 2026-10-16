"""P017 independently sourced ACE FY25 versus FY26 original cash timing tests."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.hg009_p017_ace_cash import (
    EXPECTED_RUPEES,
    FIELDS,
    FIRST_RECEIPT,
    build_ace_fy25_fy26_cash_audit,
    capture_fy25_ace,
    extract_ace_fy25_original,
    verify_ace_fy25_fy26_cash_audit,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "research/hg009/hg009-p017-ace-two-year-cash-bridge-v1.json"


def _fake_original(
    *, symbol: str = "ACE", unit: str = "INR (in Actuals)",
    changes: dict[str, str] | None = None,
) -> bytes:
    modified = {**EXPECTED_RUPEES, **(changes or {})}
    sections = {
        "operating": "Cash flows from used in operating activities",
        "investing": "Cash flows from used in investing activities",
        "financing": "Cash flows from used in financing activities",
    }
    rows = []
    for section, name in sections.items():
        rows.append(f"<tr><td>{name}</td><td></td></tr>")
        for key, (group, label) in FIELDS.items():
            if group != section:
                continue
            original = modified[key]
            amount = f"({original[1:]})" if original.startswith("-") else original
            rows.append(
                f"<tr><td>{label}</td><td>{amount}</td></tr>"
            )
    return (
        "<html><body>"
        f"<p>NSE Symbol {symbol} ISIN INE731H01025</p>"
        f"<p>Description of presentation currency {unit}</p>"
        "<p>Date of end of financial year 31-Mar-2025</p>"
        "<p>Nature of report standalone or consolidated Consolidated</p>"
        "<p>Whether results are audited or unaudited Audited</p>"
        # Real NSE original iXBRL pages contain substantial filing metadata.
        # Keep the production >=2 KB sanity gate intact instead of weakening
        # it just to admit an unrealistically short in-memory fixture.
        "<section><p>Independent original-filing metadata for the "
        "issuer's consolidated financial reporting period.</p>"
        + ("<p>Original filing presentation detail with no financial "
           "statement values.</p>" * 8)
        + "</section>"
        "<table><tr><td>Statement of cash flows</td><td></td></tr>"
        + "".join(rows)
        + "</table></body></html>"
    ).encode()


def test_rupees_vs_lakhs_are_not_silently_equated():
    source = _fake_original()
    extracted = extract_ace_fy25_original(source)
    assert len(extracted) == len(FIELDS) == 16
    assert extracted["cfo"] == 4_119_800_000
    assert extracted["ppe_cash_purchase"] == 2_210_000_000
    assert extracted["net_investing"] == -3_826_900_000
    assert extracted["net_financing"] == -289_900_000
    assert extracted["cash_change"] == 6_300_000
    assert extracted["cash_end"] - extracted["cash_begin"] == 6_300_000
    with pytest.raises(AlphaContractError, match="currency"):
        extract_ace_fy25_original(
            _fake_original(unit="INR (in Lakhs)")
        )


def test_fy25_original_wrong_source_identity_or_single_row_value_is_rejected():
    with pytest.raises(AlphaContractError, match="issuer"):
        extract_ace_fy25_original(_fake_original(symbol="OTHERCOMPANY"))
    with pytest.raises(AlphaContractError, match="changed original"):
        extract_ace_fy25_original(
            _fake_original(changes={"cfo": "4119800001"})
        )


def test_original_receipt_uses_actual_observation_and_content_address(tmp_path: Path):
    raw = _fake_original()
    result = capture_fy25_ace(
        fetch=lambda url: (200, raw),
        observed_at=datetime(2026, 10, 16, 5, 30, tzinfo=UTC),
        root=tmp_path,
    )
    assert result["state"] == "ORIGINAL_NSE_FY25_CONSOLIDATED_CASHFLOW_REPLAYED"
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["observed_at_utc"] == "2026-10-16T05:30:00+00:00"
    assert gzip.decompress((
        tmp_path / result["original_archive_repo_path"]
    ).read_bytes()) == raw
    assert result["cash_flow_rows_verified"] == 16
    assert result["live_capital_allowed"] is False


def test_unavailable_original_source_does_not_claim_true_fy25_cash(tmp_path: Path):
    bad = capture_fy25_ace(
        fetch=lambda url: (403, None),
        observed_at=datetime(2026, 10, 16, 5, 30, tzinfo=UTC),
        root=tmp_path,
    )
    assert bad["state"] == "BLOCKED_ORIGINAL_NSE_HTTP"
    assert bad["raw_sha256"] is None
    assert bad["live_capital_allowed"] is False

    invalid = capture_fy25_ace(
        fetch=lambda url: (200, _fake_original(changes={"pbt": "100"})),
        observed_at=datetime(2026, 10, 16, 5, 30, tzinfo=UTC),
        root=tmp_path,
    )
    assert invalid["state"] == "BLOCKED_FY25_ISSUER_OR_FINANCIAL_ROW"
    assert invalid["raw_sha256"] is None


def test_report_build_requires_archived_original_and_signed_comparisons():
    pending = not (ROOT / FIRST_RECEIPT).exists()
    proc = subprocess.run(
        [sys.executable, "scripts/materialize_hg009_p017_ace.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if pending:
        assert proc.returncode == 0
        assert json.loads(proc.stdout)["state"] == "AWAITING_ORIGINAL_NSE_FY25_RAW_SOURCE"
        return
    # Successful archive path is independently replayed against source P013
    # and dated P015, never an artifact-only claim.
    report = build_ace_fy25_fy26_cash_audit(ROOT)
    assert report["fy25_CFO_cr"] == pytest.approx(411.98)
    assert report["fy26_CFO_cr"] == pytest.approx(417.27)
    assert report["fy25_PPE_cash_spend_cr"] == pytest.approx(221.0)
    assert report["fy26_PPE_cash_spend_cr"] == pytest.approx(93.26)
    assert report["CFO_change_component_cr"] == pytest.approx(5.29)
    assert report["PPE_spend_reduction_component_cr"] == pytest.approx(127.74)
    assert report["CFO_less_PPE_proxy_change_cr"] == pytest.approx(133.03)
    assert report["FY26_counterfactual_proxy_holding_FY25_PPE_spend_cr"] == pytest.approx(
        196.27
    )
    assert report["fy25_CFO_less_PPE_cr_not_owner_FCF"] == pytest.approx(190.98)
    assert report["fy26_CFO_less_PPE_cr_not_owner_FCF"] == pytest.approx(324.01)
    assert report["probability_weighted_50pct_future_return"] is None
    assert report["capital_eligible"] is False
    assert report["live_capital_allowed"] is False
    verify_ace_fy25_fy26_cash_audit(report, ROOT)
    if REPORT.exists():
        assert json.loads(REPORT.read_text(encoding="utf-8")) == report
        assert proc.returncode == 0
        assert json.loads(proc.stdout)["state"] == "REPLAY_VERIFIED"
