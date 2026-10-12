# H021-P019: Repair the First Complete 12 October NSE Source Chain

Status: **OFFICIAL MARKET SOURCE PROVENANCE RECONCILIATION, NO RETURNS**.
Frozen: 12 October 2026, after the original 10 NSE stock open capture
and independent double-host NSE Nifty500 source recovery.

## Actual chain

1. **9 Oct H021-P003 pre-entry intent**: ten eligible top-decile source
   signals frozen without trading capital.
2. **12 Oct first original P004 source attempt**: 10/10 original CM EQ
   stock open prices captured. Nifty 500 archive file returned HTTP404
   at the true source timestamp around 17:33 IST. The original packet
   has null index values and remains permanently intact.
3. **12 Oct P018 independent official index recovery**: after the first
   attempt, the exact 12 Oct Daily Snapshot CSV was published by NSE;
   primary archives.nseindia.com and the official nsearchives mirror
   served IDENTICAL 15,668 bytes with SHA-256
   fc847998c9d8bfa461ddad1770dc610086eadea3d442f1dfe515ae76b83c7f25.
   Nifty 500 price index OPEN 21,936.25 and CLOSE 21,822.75. Its own
   true later UTC retrieval time and immutable packet are preserved.
4. **P019 recapture**: trigger the original P004 official source workflow
   on this reviewed change and after future successful P018 runs, to
   independently obtain a complete official NSE stock+benchmark packet.
   The new full packet must use the **identical original NSE UDiFF
   stock raw SHA**, the identical ten ISINs and OHLC numbers, and the
   **identical original daily-index CSV SHA** and opening/closing
   prices recovered independently from the two NSE hosts.

## Important scientific distinction

The newly available source is a **later retrieval of the SAME session's
official index values**. The first attempt's 404 was real, cannot be
silently overwritten and must not be presented as a source captured
earlier than its true public availability.

A synthetic later-complete packet may be constructed in offline tests
to demonstrate strict reconciliation, but this is NEVER presented as
an actual NSE acquisition. The real production P004 workflow must
perform independent post-close HTTP retrieval and record its true
timestamps; only its successful real-source output can be committed
as the complete first-entry observation.

Reconciliation is rejected if:

- any of the original ten prices, OHLC/ISIN/order/source hash changed;
- a new NSE Nifty 500 source had a different SHA or value;
- the later index retrieval is dated BEFORE the independently
  verified P018 source availability;
- original P004 first packet was altered, its 404 removed, or
  P018 primary/mirror evidence changed;
- source completeness is claimed with a missing official index,
  or any real trade fill, corporate-action, dividend entitlement,
  benchmark excess, or capital permission is asserted.

Both the complete P004 source and the P019 reconciliation will be
committed append-only under the existing H021 entry-observations
directory after real post-close source acquisition.

## Code and execution

- src/marketlab/h021_first_source_reconciliation.py
- scripts/reconcile_h021_first_full_source.py
- tests/test_h021_first_source_reconciliation.py
- .github/workflows/h021-first-entry-observation.yml (reviewed update).

The update to P004 workflow triggers its first source collector on
merge through the existing exact-file push filter, even when the
normal GitHub Actions schedule may be delayed. Future P018
completion events can also retrigger it safely, but only until the
complete original result exists.

Once original P004 is genuinely source-complete, the pre-existing
P015 replay workflow can independently verify the exact original
stock+index bytes. The separate P017 EPS and dividend measurement
warnings remain operative, as do P006 Muhurat/2027 calendar blockers.

## NOT certified

- actual ability to buy at the original NSE open or complete an order;
- dividend-entitled VEDL total-return proxy or cash payout;
- source-complete stock corporate actions;
- Nifty 500 TRI versus price index comparability;
- approved 20/60-session exit calendar or realised outcomes;
- multiple prospective cohorts, multiple-testing-adjusted alpha,
  stock recommendations or capital deployment.

**Live capital stays disabled.** The original first 404 packet and
later source retrieval time both remain part of the scientific record.
