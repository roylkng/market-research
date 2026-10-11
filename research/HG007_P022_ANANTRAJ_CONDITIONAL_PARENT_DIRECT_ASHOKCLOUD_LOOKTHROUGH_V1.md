# HG007-P022: Anant Raj / Ashok Cloud Two-Layer Shareholder Look-Through

Research-only, 11 October 2026. **This is conditional arithmetic,
not a completed demerger, newco stock target, or expected return.**

## Why the original HG005 gross-value intuition is incomplete

There is a material ownership distinction between:

1. New Ashok Cloud shares issued directly to eligible Anant Raj
   shareholders under the proposed 1-for-1 demerger, and
2. Ashok Cloud shares ALREADY owned by the listed Anant Raj parent,
   which the July 21 issuer press explicitly says will not be canceled.

The future newco can have the original Anant Raj investors participating
through **both** shareholding routes. Summing all of Ashok Cloud's
enterprise value plus an unchanged valuation for the original Anant Raj
parent can double count the same company assets and future cash flows.

This project must not claim a free additional 100% data-centre valuation
from the proposed 1-for-1 entitlement alone.

## Pinning original issuer facts

Exact original NSE July 20, July 21 subscription-completion, and
July 21 scheme press PDFs were captured by HG007-P021, with hashes
locked in Git.

The original sources confirm:

| Term | Filed value | Original issuer source |
|---|---:|---|
| Existing parent-owned ACPL shares before July rights issue | 250,000 | July 20 PDF page 1 |
| Further shares subscribed and later confirmed acquired | 374,322,553 | July 20 PDF page 1 and July 21 update page 1 |
| Cash amount for subscription at ₹2 face value | ₹74.8645106 crore | July 20 and 21 PDFs |
| Resulting parent-held Ashok Cloud shares | **374,572,553** | July 20 proposal plus July 21 subscription completion |
| Proposed new share for each eligible existing Anant Raj share | **1** | July 21 scheme press page 4 |
| Cancellation of existing parent Ashok Cloud holding | **No** | July 21 scheme press page 4 |
| Court/shareholder/creditor/stock exchange approvals required | **Yes** | July 21 scheme press page 4 |

The source documents are not a court order effective-date
certificate or an audited breakdown of assets, cash and liabilities.

## Why 359,876,930 is a PROXY, not verified record-date shares

Original HG005-D001 records ₹20,795.48840005 crore market cap and
₹577.85 raw NSE price on 1 October 2026. Their quotient yields
**359,876,930**, HG005's historical reported fully diluted share
denominator. Public June 30 shareholding summaries also show
359,876,930 fully paid-up shares.

That agreement does NOT prove the actual future demerger entitlement
record-date **basic** share count or its diluted securities are
identical. The final record date, court order, issue of new instruments,
eligible holdings and rights are still unknown.

P022 freezes exactly one explanatory scenario under these conditional
assumptions:

- parent retains ALL its 374,572,553 existing Ashok Cloud shares;
- future Anant Raj entitlement basic shares equal the frozen historical
  proxy of 359,876,930;
- all those eligible parent shareholders get exactly one new Ashok
  Cloud ordinary voting share each;
- no other Ashok Cloud securities, rights, transfers, or capital
  increases change the denominator;
- parent retained shares and newly distributed shares have the same
  economic/voting class and no special claims.

Then:

    Ashok Cloud total illustrative shares
    = 374,572,553 + 359,876,930
    = 734,449,483 shares

    Parent retained economic share
    = 374,572,553 / 734,449,483
    = 51.0004516%

    Direct issue economic share to original ARL holders
    = 359,876,930 / 734,449,483
    = 48.9995484%

This is consistent with management's statement that Ashok Cloud would
remain a subsidiary under the proposed transaction. The actual future
vote/control outcome and share classes still need original approval
and capitalization evidence.

## Look-through conservation and double counting

For **one** original ANANTRAJ share, in the simplified scenario:

    Direct ACPL shares received = 1

    Indirect ACPL shares via ARL = 374,572,553 / 359,876,930
                                = 1.040835135 (economic equivalent)

    Combined proportional ACPL claim
    = (1 + 1.040835135) / 734,449,483
    = 1 / 359,876,930 of ACPL total equity.

This identity is not a stock price and is not an argument against
value unlocking from a future listing. It simply prevents counting
the same underlying shareholder claim twice.

Separately listed securities may trade at different multiples, have
different governance rights, and attract equity funding, but this
does not create extra shares of productive assets from the
distribution alone. Transfers, financing, taxes, liabilities,
transaction costs, market pricing and minority discounts can change
economic outcomes materially.

## Required future underwriting model

A future source-verified sum-of-parts must construct:

- **Post-scheme Anant Raj equity** = value of remaining real estate
  operations (less their transferred/external debt and other claims)
  PLUS correctly attributed value of its retained Ashok Cloud
  ownership MINUS holding-company overhead/taxes/discount where
  justified.
- **Direct shareholder entitlement** = observed independent price
  of the actual number/class of Ashok Cloud shares received by
  an eligible Anant Raj shareholder, net of any costs/tax effects.
- **Total portfolio equity change** = combined value of post-scheme
  original ANANTRAJ holding + actual newco entitlement MINUS the
  appropriate matched-date old ANANTRAJ cum-transaction value.

No double-count of original cloud earnings, parent intercompany assets,
gross newco equity, paid-up share capital, or debt/cash transfers is allowed.

The historic HG005-D003 ~10% gross data-centre sensitivity
is **not** a transaction profit estimate and is not amended. The
unknown transferred net debt and missing carve-out FCF remain blockers.

## Implementation

- src/marketlab/hg007_anantraj_lookthrough.py
- scripts/build_hg007_anantraj_lookthrough.py
- tests/test_hg007_anantraj_lookthrough.py
- .github/workflows/hg007-anantraj-lookthrough.yml
- Result after main merge:
  research/hg007/anantraj-july2026-originals/
  conditional-parent-direct-newco-ownership-v1.json

All three source PDFs and the HG005-v1 original are verified byte-for-byte
before calculation; altered source page text, history share denominators,
missing original source, invalid original legal stage and fabricated value
targets are rejected by regression tests.

**No investment recommendation, fully approved scheme, current
share count, stock return outcome, probability, or capital allocation
is authorized.**
