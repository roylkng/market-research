"""L001 contracts: no forward label without full horizons and action records."""

from dataclasses import replace
from hashlib import sha256

from marketlab.l001_long_horizon import (
    BASES,
    ReturnObservation,
    ValueFact,
    long_horizon_return_label,
    reverse_value_creation_hurdle,
)

CUTOFF = "2026-10-17T10:00:00Z"


def facts():
    amounts = {
        "price": 100.0,
        "diluted_shares": 10.0,
        "owner_cash": 50.0,
        "excess_cash": 100.0,
        "net_claims": 20.0,
        "nopat_prior": 100.0,
        "nopat_current": 140.0,
        "capital_prior": 300.0,
        "capital_current": 500.0,
    }
    return {
        role: ValueFact(
            role=role,
            symbol="TEST",
            isin="INE000000001",
            value_cr=amounts[role],
            accounting_basis=BASES[role],
            original_bytes=role.encode(),
            sha256_digest=sha256(role.encode()).hexdigest(),
            published_at_utc="2026-10-16T10:00:00Z",
            first_seen_at_utc="2026-10-16T10:01:00Z",
            reviewer_status="INDEPENDENTLY_REVIEWED",
        )
        for role in BASES
    }


def evaluate(items=None, *, multiple=15.0):
    return reverse_value_creation_hurdle(
        symbol="TEST",
        isin="INE000000001",
        decision_cutoff_utc=CUTOFF,
        facts=facts() if items is None else items,
        annual_discount=0.12,
        terminal_owner_cash_multiple=multiple,
        years=3,
    )


def label(**changes):
    values = {
        "symbol": "TEST",
        "isin": "INE000000001",
        "horizon_sessions": 252,
        "elapsed_verified_sessions": 252,
        "entry_price_inr": 100.0,
        "exit_price_inr": 55.0,
        "shares_per_initial_share": 2.0,
        "distributions_per_initial_share_inr": 5.0,
        "settlement_per_initial_share_inr": None,
        "benchmark_tr_entry_open": 100.0,
        "benchmark_tr_exit_close": 110.0,
        "corporate_action_status": "FULLY_RECONCILED",
        "exit_status": "ACTIVE",
        "entry_tradable": True,
        "roundtrip_cost_fraction": 0.01,
        "calendar_receipt_sha256": "a" * 64,
    }
    values.update(changes)
    return long_horizon_return_label(ReturnObservation(**values))


def test_reverse_growth_hurdle_and_incremental_roic():
    result = evaluate()
    assert result["status"] == "REVERSE_HURDLE_MATH_ONLY"
    assert result["incremental_nopat_on_net_invested_capital"] == 0.20
    assert result["annual_owner_cash_growth_hurdle"] > 0
    assert result["investment_authorized"] is False


def test_higher_cash_multiple_lowers_required_growth():
    assert evaluate(multiple=20)["annual_owner_cash_growth_hurdle"] < (
        evaluate(multiple=12)["annual_owner_cash_growth_hurdle"]
    )


def test_source_digest_mutation_denied():
    items = facts()
    items["price"] = replace(items["price"], original_bytes=b"altered")
    assert "price_bytes_not_authenticated" in evaluate(items)["reasons"]


def test_after_cutoff_filing_denied():
    items = facts()
    items["owner_cash"] = replace(
        items["owner_cash"], first_seen_at_utc="2026-10-17T11:00:00Z",
    )
    assert evaluate(items)["status"] == "ABSTAIN"


def test_out_of_scope_cfo_minus_ppe_denied():
    items = facts()
    items["owner_cash"] = replace(
        items["owner_cash"], accounting_basis="CFO_LESS_PPE",
    )
    assert "owner_cash_accounting_basis_unreconciled" in evaluate(items)["reasons"]


def test_wrong_identity_denied():
    items = facts()
    items["diluted_shares"] = replace(items["diluted_shares"], isin="INEWRONG")
    assert evaluate(items)["status"] == "ABSTAIN"


def test_source_review_is_required_but_not_proof_of_truth():
    items = facts()
    items["owner_cash"] = replace(
        items["owner_cash"], reviewer_status="SELF_DECLARED",
    )
    assert evaluate(items)["status"] == "ABSTAIN"
    assert evaluate()["accounting_truth_certified_by_code"] is False


def test_nonpositive_or_zero_incremental_capital_denied():
    items = facts()
    items["capital_current"] = replace(items["capital_current"], value_cr=300.0)
    assert "positive_net_incremental_capital_required" in evaluate(items)["reasons"]


def test_cash_claims_and_cash_surplus_affect_hurdles():
    base = evaluate()["annual_owner_cash_growth_hurdle"]
    items = facts()
    items["net_claims"] = replace(items["net_claims"], value_cr=200.0)
    assert evaluate(items)["annual_owner_cash_growth_hurdle"] > base
    items = facts()
    items["excess_cash"] = replace(items["excess_cash"], value_cr=200.0)
    assert evaluate(items)["annual_owner_cash_growth_hurdle"] < base


def test_long_horizon_never_matures_early():
    out = label(elapsed_verified_sessions=251)
    assert out["status"] == "NOT_MATURE"
    assert "gross_stock_total_return" not in out


def test_exact_split_dividend_and_benchmark_return():
    out = label()
    assert out["status"] == "TOTAL_RETURN_MATH_ONLY"
    assert out["gross_stock_total_return"] == 0.15
    assert out["net_stock_return_cost_stress"] == 0.14
    assert out["benchmark_total_return"] == 0.10
    assert out["net_excess_return_cost_stress"] == 0.04
    assert out["label_may_join_frozen_prospective_outcomes"] is False


def test_delisting_settlement_loss_retained():
    out = label(
        exit_status="SETTLED_DELISTING",
        exit_price_inr=None,
        settlement_per_initial_share_inr=40.0,
        shares_per_initial_share=1.0,
        distributions_per_initial_share_inr=0.0,
    )
    assert out["status"] == "TOTAL_RETURN_MATH_ONLY"
    assert out["gross_stock_total_return"] == -0.60


def test_delisted_without_settlement_abstains():
    assert label(exit_status="SETTLED_DELISTING", exit_price_inr=None)["status"] == "ABSTAIN"


def test_action_rights_unresolved_abstains():
    assert label(corporate_action_status="RIGHTS_UNRESOLVED")["status"] == "ABSTAIN"


def test_untradeable_entry_is_not_fabricated():
    assert label(entry_tradable=False)["status"] == "NOT_EXECUTABLE"


def test_exit_off_by_one_blocked():
    assert label(elapsed_verified_sessions=253)["status"] == "ABSTAIN"


def test_invalid_dividends_nan_is_missing_not_zero():
    assert label(distributions_per_initial_share_inr=float("nan"))["status"] == "ABSTAIN"


def test_wrong_horizon_rejected():
    assert label(horizon_sessions=20)["status"] == "ABSTAIN"
