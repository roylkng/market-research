"""L001 P008 strictly retains original company and timestamp evidence."""

from __future__ import annotations

from datetime import datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p008_crossplane import (
    PINS,
    _by_symbol,
    _pin,
    _same_amount,
    _timestamp,
    crossplane_diagnostic,
)


def test_all_five_pinned_input_digests_are_immutable_sha256():
    assert set(PINS) == {"p004", "p005", "p006", "p007", "oct15"}
    assert len(set(PINS.values())) == 5
    assert all(len(value) == 64 for value in PINS.values())


def test_original_document_resigning_cannot_bypass_pins():
    base = {"symbol": "ACE", "information_set": "original"}
    signature = digest(base)
    _pin({**base, "report_sha256": signature}, "report_sha256", signature)
    changed = {**base, "information_set": "posthoc"}
    changed["report_sha256"] = digest(changed)
    with pytest.raises(AlphaContractError, match="immutable"):
        _pin(changed, "report_sha256", signature)


def test_source_identity_does_not_allow_duplicate_or_short_universe():
    with pytest.raises(AlphaContractError, match="100-company"):
        _by_symbol([{"symbol": "ACE", "isin": "INE731H01025"}], "FA001")
    rows = [
        {"symbol": f"S{i:04d}", "isin": "INE731H01025"} for i in range(100)
    ]
    rows[1]["symbol"] = rows[0]["symbol"]
    with pytest.raises(AlphaContractError, match="duplicate"):
        _by_symbol(rows, "FA001")


def test_exact_utc_and_annual_original_figure_agreement():
    dt = _timestamp("2026-10-15T17:21:34.130436Z")
    assert dt == datetime.fromisoformat("2026-10-15T17:21:34.130436+00:00")
    for value in ("2026-10-15T17:21:34", "bogus", "2026-10-15T22:51:34+05:30"):
        with pytest.raises(AlphaContractError, match="UTC"):
            _timestamp(value)
    assert _same_amount(417.27, 417.27)
    assert not _same_amount(417.27, 999.0)
    assert not _same_amount(None, 0)


def test_prospective_opportunity_cannot_be_claimed_from_empty_sources():
    with pytest.raises(AlphaContractError):
        crossplane_diagnostic({}, {}, {}, {}, {})
