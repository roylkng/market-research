# AE001 D002 NSE FO UDiFF Unit Audit v1

Status: SOURCE-SEMANTICS AUDIT ONLY
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Verify the numeric-unit assumptions used by T005 stock-futures features before
any T005 model fit or outcome metric is opened.

D002 opens no equity return labels.

## Exact reference source

NSE F&O UDiFF Common Bhavcopy Final for 2026-09-25:

BhavCopy_NSE_FO_0_0_0_20260925_F_0000.csv.zip

This is the same D001 source session.

## Frozen audit checks

For every structurally valid STF row:

### Open interest unit check

Require:

    OpnIntrst / NewBrdLotQty

to be integral within 1e-9 for every row with positive lot size.

Likewise require:

    ChngInOpnIntrst / NewBrdLotQty

to be integral within 1e-9.

Interpretation if passed:

OpnIntrst and ChngInOpnIntrst are underlying-equivalent units while board lot
converts them to contract counts.

### Traded-volume unit check

For every traded STF row with:

- TtlTradgVol > 0;
- TtlTrfVal > 0;
- NewBrdLotQty > 0;
- HghPric > 0;
- LwPric > 0;

compute:

    implied_average_futures_price =
        TtlTrfVal / (TtlTradgVol * NewBrdLotQty)

Require the implied price to fall inside [LwPric, HghPric], allowing an absolute
rounding tolerance of INR 0.02.

Interpretation if passed:

TtlTradgVol is contract count and TtlTrfVal is rupee notional compatible with
contract count times board lot times futures price.

## T005 consequence

If all checks pass, the existing frozen features remain unchanged:

- fut_total_volume_to_oi uses
  sum(TtlTradgVol * NewBrdLotQty) / sum(OpnIntrst);

- fut_notional_to_cash_turnover uses
  sum(TtlTrfVal) / same-session cash TtlTrfVal.

If D002 fails materially, T005 remains blocked. No unit repair may be made after
a T005 model metric is opened.

## Evidence

D002 must record:

- exact source URL;
- raw SHA-256;
- STF row count;
- OI divisibility violation count/max residual;
- change-OI divisibility violation count/max residual;
- traded-row price-identity observation count;
- price-range violation count/max violation.

No outcome labels are opened.
