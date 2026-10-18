"""L001 P010: adversarial tests for capital-claims and legal buyback math."""

from dataclasses import replace

from marketlab.l001_p010_asset_claims import (
    BuybackObservation,
    HoldingCompanyObservation,
    InternalGroupTransfer,
    ReceivableSettlement,
    buyback_nav_sensitivity,
    creditor_recovery_reconciliation,
    holding_company_sensitivity,
    internal_group_asset_transfer,
)


def zuari(**changes):
    fields = {
        "symbol": "ZUARIIND",
        "price_date": "2026-10-15",
        "financial_position_date": "2026-03-31",
        "investments_date": "2026-06-30",
        "price_inr": 267.55,
        "reported_basic_shares": 29_781_184,
        "listed_stake_mtm_cr": 4223.0,
        "financial_borrowings_cr": 2581.29,
        "cash_equivalents_cr": 61.8655,
        "pledged_largest_stake_shares": 33_975_444,
        "total_largest_stake_shares": 59_475_924,
        "largest_stake_reference_quote_inr": 468.0,
        "financing_interest_paid_cr": 230.601,
        "operating_cashflow_cr": 143.7594,
        "ppe_cash_purchase_cr": 25.7392,
        "lease_cash_paid_cr": 3.9431,
    }
    fields.update(changes)
    return HoldingCompanyObservation(**fields)


def shipping(**changes):
    fields = {
        "symbol": "GESHIP",
        "price_date": "2026-10-15",
        "issuer_nav_date": "2026-06-30",
        "cancellation_date": "2026-10-10",
        "old_shares": 142_767_161,
        "legally_extinguished_shares": 1_858_941,
        "purchased_after_cancellation_not_yet_extinguished": 849_719,
        "quoted_price_inr": 1484.1,
        "issuer_nav_low_inr": 1862,
        "issuer_nav_mid_inr": 1886,
        "issuer_nav_high_inr": 1911,
        "cash_spent_on_cancelled_lot_cr": 262.714745815,
    }
    fields.update(changes)
    return BuybackObservation(**fields)


def test_zuari_historical_stake_discount_does_not_prove_equity_value():
    result = holding_company_sensitivity(zuari())
    assert result["status"] == "POSTHOC_SUM_OF_PARTS_FALSIFICATION_ONLY"
    assert result["historical_basic_equity_cap_cr"] == 796.795578
    assert result["historical_net_borrowings_less_cash_cr"] == 2519.4245
    assert result["illustrative_listed_assets_minus_net_borrowings_cr"] == 1703.5755
    assert abs(result["listed_asset_haircut_that_matches_price_no_other_assets"] - .21472411) < 1e-7
    assert abs(result["pledged_fraction_largest_stake"] - .57124701) < 1e-7
    assert result["pledged_stake_gross_mtm_cr_not_extra_liability"] == 1590.050779
    assert result["historic_cfo_minus_ppe_cr_not_owner_cash"] == 118.0202
    assert result["historic_cfo_less_ppe_interest_and_leases_cr_not_owner_cash"] == -116.5239
    assert result["investment_authorized"] is False
    assert result["expected_return"] is None


def test_zuari_haircut_20_percent_removes_apparent_margin_of_safety():
    result = holding_company_sensitivity(zuari())
    scenario = next(
        x for x in result["scenarios"]
        if x["listed_asset_mark_to_market_haircut"] == .2
    )
    assert scenario["simplified_residual_cr_not_shareholder_value"] == 858.9755
    assert scenario["residual_relative_to_historical_basic_equity_fraction_not_expected_return"] < .08


def test_zuari_future_asset_data_or_pseudodebt_rejected():
    assert holding_company_sensitivity(
        replace(zuari(), investments_date="2026-11-01")
    )["status"] == "ABSTAIN"
    assert holding_company_sensitivity(
        replace(zuari(), pledged_largest_stake_shares=60_000_000)
    )["status"] == "ABSTAIN"
    assert holding_company_sensitivity(
        replace(zuari(), financial_borrowings_cr=float("nan"))
    )["status"] == "ABSTAIN"
    assert holding_company_sensitivity(zuari(), investment_haircuts=(1.2,))[
        "status"
    ] == "ABSTAIN"


def test_only_canceled_geship_shares_change_legal_denominator():
    result = buyback_nav_sensitivity(shipping())
    assert result["status"] == "POSTHOC_CROSS_DATE_BUYBACK_NAV_MATH_ONLY"
    assert result["issued_shares_after_extinguishment"] == 140_908_220
    assert result["subsequent_purchased_not_yet_canceled_in_legal_denominator"] == 849_719
    assert result["historical_basic_equity_cap_cr_at_oct_price"] == 20912.18893
    assert abs(result["midpoint_nav_accretion_from_september_lot_only_inr"] - 6.236792) < 1e-6
    assert abs(result["post_cancellation_nav_per_share_as_if_no_other_changes"] - 1892.236792) < 1e-6
    assert result["issuer_nav_original_bytes_authenticated"] is False
    assert result["investment_authorized"] is False


def test_geship_uncanceled_purchase_does_not_inflate_denominator_adjustment():
    baseline = buyback_nav_sensitivity(shipping())
    updated = buyback_nav_sensitivity(
        shipping(purchased_after_cancellation_not_yet_extinguished=1_100_000)
    )
    assert updated["issued_shares_after_extinguishment"] == baseline[
        "issued_shares_after_extinguishment"
    ]
    assert updated["post_cancellation_nav_per_share_as_if_no_other_changes"] == baseline[
        "post_cancellation_nav_per_share_as_if_no_other_changes"
    ]


def test_geship_rejects_future_cancellation_and_spurious_nav():
    assert buyback_nav_sensitivity(
        shipping(cancellation_date="2026-10-16")
    )["status"] == "ABSTAIN"
    assert buyback_nav_sensitivity(
        shipping(legally_extinguished_shares=142_767_161)
    )["status"] == "ABSTAIN"
    assert buyback_nav_sensitivity(
        shipping(issuer_nav_low_inr=1950)
    )["status"] == "ABSTAIN"


def test_zuari_agro_fully_settled_prior_258_50_cr_receivable():
    item = ReceivableSettlement(
        debtor="ZUARI",
        creditor="ZUARIIND",
        outstanding_before_cr=258.50,
        first_payment_cr=214.50,
        first_payment_date="2026-09-18",
        final_payment_cr=44.0,
        final_payment_date="2026-09-30",
        source_first=(
            "https://www.zuari.in/assets/files/"
            "ZACLDisclosureunderReg30-RepaymentofICDs-18-09-2026.pdf"
        ),
        source_final=(
            "https://www.zuari.in/assets/files/"
            "Reg30RepaymentofICDsdtd30.09.2026.pdf"
        ),
    )
    original = holding_company_sensitivity(zuari())
    output = creditor_recovery_reconciliation(
        item, research_cutoff_date="2026-10-15",
        reference_basic_equity_cap_cr=original["historical_basic_equity_cap_cr"],
    )
    assert output["status"] == "ISSUER_COUNTERPARTY_DISCLOSED_FULL_RECEIVABLE_RECOVERY"
    assert output["recovered_receivable_cr"] == 258.5
    assert output["remaining_reported_receivable_cr"] == 0
    assert abs(output["payment_as_fraction_of_old_basic_equity_cap"] - .324423) < .00001
    assert output["new_shareholder_wealth_from_debt_to_cash_reclassification_cr"] == 0
    assert output["bank_credit_independently_verified"] is False
    assert output["creditor_external_debt_repayment_independently_verified"] is False
    assert output["investment_authorized"] is False


def test_zuari_agro_repayment_unconfirmed_or_future_inadmissible():
    from dataclasses import replace

    settlement = ReceivableSettlement(
        debtor="ZUARI",
        creditor="ZUARIIND",
        outstanding_before_cr=258.5,
        first_payment_cr=214.5,
        first_payment_date="2026-09-18",
        final_payment_cr=44,
        final_payment_date="2026-09-30",
        source_first="https://www.zuari.in/first.pdf",
        source_final="https://www.zuari.in/last.pdf",
    )
    assert creditor_recovery_reconciliation(
        replace(settlement, final_payment_cr=50),
        research_cutoff_date="2026-10-15",
        reference_basic_equity_cap_cr=796.795578,
    )["status"] == "ABSTAIN"
    assert creditor_recovery_reconciliation(
        settlement, research_cutoff_date="2026-09-20",
        reference_basic_equity_cap_cr=796.795578,
    )["status"] == "ABSTAIN"


def test_zuari_texinfra_direct_transfer_is_not_new_consolidated_units():
    transfer = InternalGroupTransfer(
        parent="ZUARIIND",
        wholly_owned_seller="ZUARI INTERNATIONAL LIMITED",
        listed_issuer="TEXINFRA",
        transaction_date="2026-09-23",
        acquired_target_shares=12_810_900,
        parent_shares_before=26_480_712,
        subsidiary_shares_before=12_810_900,
        purchase_cost_cr=147.96,
        source_uri="https://bazaarwatch.com/announcement/138972",
    )
    result = internal_group_asset_transfer(
        transfer, research_cutoff_date="2026-10-15"
    )
    assert result["status"] == "INTRAGROUP_TRANSFER_NOT_NEW_GROUP_EQUITY_UNITS"
    assert result["parent_direct_shares_after"] == 39_291_612
    assert result["subsidiary_shares_after"] == 0
    assert result["consolidated_shares_before"] == 39_291_612
    assert result["consolidated_shares_after"] == 39_291_612
    assert result["net_new_group_shares"] == 0
    assert result["investment_authorized"] is False


def test_group_transfer_with_unproven_seller_inventory_abstains():
    transfer = InternalGroupTransfer(
        parent="ZUARIIND", wholly_owned_seller="ZUARI INTERNATIONAL LIMITED",
        listed_issuer="TEXINFRA", transaction_date="2026-09-23",
        acquired_target_shares=12_810_900,
        parent_shares_before=26_480_712,
        subsidiary_shares_before=1_000,
        purchase_cost_cr=147.96, source_uri="https://example.org/filing.pdf"
    )
    assert internal_group_asset_transfer(
        transfer, research_cutoff_date="2026-10-15"
    )["status"] == "ABSTAIN"
