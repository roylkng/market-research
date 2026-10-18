"""P013: original Q1 exceptional-item bridge and fail-closed evidence tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.l001_p013_exceptional_profit import (
    P004_SHA,
    P007_SHA,
    _bound_original,
    _facts_equal,
    _utc,
    exceptional_component,
    exceptional_profit_replay,
)


def test_mmfl_issuer_q1_statement_math_not_normalized_after_tax():
    sign, share, alert = exceptional_component(
        35.0696, 56.252, 91.3216, nbfc_form=False,
    )
    assert sign == "POSITIVE"
    assert round(100 * share, 2) == 61.6
    assert alert is True


def test_mindacorp_consolidation_gain_math_not_pat_adjustment():
    sign, share, alert = exceptional_component(
        112.98, 123.99, 236.97, nbfc_form=False,
    )
    assert sign == "POSITIVE"
    assert round(100 * share, 2) == 52.32
    assert alert is True


def test_negative_exceptional_and_zero_events():
    result = exceptional_component(8.517, -1.522, 6.995, nbfc_form=False)
    assert result[0] == "NEGATIVE"
    assert result[1] < 0
    assert result[2] is False
    assert exceptional_component(91.99, 0, 91.99, nbfc_form=False) == (
        "NONE_REPORTED", 0.0, False,
    )


def test_nbfc_cannot_be_promoted_to_industrial_pbt_review():
    sign, share, alert = exceptional_component(
        40, 60, 100, nbfc_form=True,
    )
    assert sign == "POSITIVE"
    assert share == 0.6
    assert alert is False


def test_pbt_nonlinear_tax_adjustment_is_not_hardcoded():
    with pytest.raises(AlphaContractError, match="does not reconcile"):
        exceptional_component(35.0696, 56.252, 90.4244, nbfc_form=False)
    for amount in (float("nan"), float("inf")):
        with pytest.raises(AlphaContractError):
            exceptional_component(amount, 1, 2, nbfc_form=False)
    with pytest.raises(AlphaContractError):
        exceptional_component(2, 1, 3, nbfc_form="false")


def test_negative_or_zero_pbt_produces_no_false_positive_ratio():
    sign, share, alert = exceptional_component(
        -20, 10, -10, nbfc_form=False,
    )
    assert sign == "POSITIVE"
    assert share is None
    assert alert is False


def test_exact_source_fact_vector_preserves_missing_not_zero():
    a = {"revenue_operations": 100.123456, "other_income": None}
    b = {"revenue_operations": 100.123457, "other_income": None}
    assert _facts_equal(a, b)
    assert not _facts_equal(a, {**b, "other_income": 0})
    assert not _facts_equal(a, {"revenue_operations": 100.123456})


def test_report_hash_pin_not_bypassed_by_regenerated_signature():
    doc = {"source": "original"}
    sha = digest(doc)
    _bound_original({**doc, "report_sha256": sha}, sha=sha, tag="test")
    changed = {"source": "fabricated"}
    changed["report_sha256"] = digest(changed)
    with pytest.raises(AlphaContractError, match="not pinned"):
        _bound_original(changed, sha=sha, tag="test")
    assert P004_SHA != P007_SHA


def test_exact_utc_and_original_publication_date():
    assert _utc("2026-08-14T15:13:21Z") == datetime.fromisoformat(
        "2026-08-14T15:13:21+00:00"
    )
    for value in ("2026-08-14T15:13:21", "2026-08-14T20:43:21+05:30", "bogus"):
        with pytest.raises(AlphaContractError):
            _utc(value)


def test_empty_or_mutated_original_panels_cannot_create_signals():
    with pytest.raises(AlphaContractError):
        exceptional_profit_replay({}, {}, {})
