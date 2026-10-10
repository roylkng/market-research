# HG007-P002: INOXGREEN/WWIL Funding, Conversion and Minority-Interest Bridge

**Status: PROVISIONAL, SOURCE REVIEW NOT APPROVED, NOT A STOCK VALUATION.**
Research snapshot: **10 October 2026**, using a transcription of the
listed company's **7 October 2026** Regulation 30 filing.

## Why this is material

The first HG007 source-pinned backlog correctly blocked a payoff/expected
return for INOXGREEN because WWIL cash generation, completion conditions
and funding were not proven under HG005's original cutoffs.

A **newer 7 October filing transcription** provides *some* capital-stack
information. It changes what to investigate but **does not make the
acquisition legally complete, profitable or investable**. The unverified
financing amounts must not be silently represented as original-source-
audited facts.

Sources:

- BSE original attachment:
  https://www.bseindia.com/xml-data/corpfiling/AttachLive/d3241df5-32e2-4476-8075-bb5ed130e697.pdf
- Third-party full-document transcription, 7 October:
  https://bazaarwatch.com/announcement/197190/inox-green-energy-services-ltd-update-on-the-resolution-plan-for-wind-world-india-limited-and-invest
- Independent third-party filing summary:
  https://www.arthneeti.com/announcements/inox-green-energy-services-ltd-update-on-the-resolution-plan-for-wind-world-india-limited-and-investment-in-vibhav-energy-private-limited-a-wholly-own-07-oct-2026

The original BSE PDF endpoint returned **403** when checked at review
time. The original document's full text and SHA-256 have **not** been
independently audited. The HTML transcription is a research lead,
not a replacement for source approval.

## What the 7 October filing appears to disclose

The transcribed filing reports a Business Transfer Agreement for WWIL's
wind operations-and-maintenance undertaking. Vibhav Energy paid
₹550 crore on 6 October, but the company explicitly says transfer
completion remains subject to BTA conditions precedent.

| Source-described funding leg | ₹ crore | Economic classification |
|---|---:|---|
| INOXGREEN subscription to Vibhav ordinary equity | 250 | Equity-funded contribution to subsidiary |
| INOXGREEN inter-company deposit to Vibhav | 200 | Group-internal loan, ₹50 scheduled for future securities conversion |
| Authum inter-company deposit to Vibhav | 100 | Outside funding, scheduled for future securities conversion |
| **Total consideration funding** | **550** | **Payment is not proof of completed legal transfer** |

Parent INOXGREEN reports ₹450 crore funded to the purchase vehicle;
the ₹100 crore balance comes from Authum, an outside participant.

The filing transcription says Vibhav has approximately ₹250.01 crore
paid-up equity immediately after the ₹250 crore cash equity subscription,
and is currently wholly owned by Inox Green. The proposed future
securities conversions have not been independently verified as completed.

## Conditional share-capital dilution illustration

If, and **only if**, the proposed ₹50 crore parent loan conversion and
₹100 crore Authum conversion both become ordinary equity **at par**,
the illustrative equity capital would be:

- INOXGREEN ordinary equity: ₹250.01 crore + ₹50 crore = ₹300.01 crore.
- Authum ordinary equity: ₹100 crore.
- Total: ₹400.01 crore.
- Parent equity interest: 300.01 / 400.01 ≈ **75%**.
- Authum equity interest: 100 / 400.01 ≈ **25%**.
- Inox group's original ₹200 crore inter-company deposit would have
  ₹150 crore outstanding after a hypothetical ₹50 crore conversion.

**Conversion at par, timing and final securities class are not verified.**
A conversion at a different valuation or into a different class could
produce materially different ownership and payment rights. The
company's press summary has separately cited an eventual 75% Vibhav
stake, but press descriptions do not establish the effective diluted
ordinary-equity denominator or cash-flow attribution.

An inter-company loan or its interest is eliminated on fully
consolidated group accounts. It cannot be counted both as a separate
third-party asset and as extra consolidated acquisition value.

## Implications for hidden-gem underwriting

1. **The acquisition is not yet source-proven closed.** The payment
   milestone must not be relabeled as completed transfer or full
   operational integration.
2. **Ownership matters:** parent-attributable equity earnings and
   distributable cash could differ from consolidated subsidiary EBITDA.
3. **The funding split is a lead, not full proof:** bank obligations,
   related-party terms, debt funding at Inox Green, unsecured loan
   covenants and consideration adjustments require original BTA/annexure
   review.
4. **The headline 2x EBITDA claim is not normalized current EBITDA.**
   Management's post-synergy EBITDA reference is forward-looking;
   neither FY26 acquired EBITDA nor cash conversion was independently
   sourced by HG005.
5. **Shareholder denominator requires a new cutoff:** Inox Green also
   disclosed a September 2026 QIP. The October 1 market capitalization
   from HG005 is not a current independently verified entry valuation.

No 75% equity share, multiple, market-price change, 550 crore payment
or 4.5 GW of acquired service capacity proves positive shareholder
returns. The downside may include integration failure, working capital,
counterparty credit, renewal attrition, legal closing costs and dilution.

## Reproducible conditional bridge

    python scripts/build_hg007_wwil_bridge.py \
      --out /tmp/wwil-conditional-financing.json

Model: src/marketlab/hg007_wwil_bridge.py
Tests: tests/test_hg007_wwil_bridge.py

The code rejects mismatched consideration sums, impossible loan
conversion amounts, attempts to promote an unaudited transcription to
original-source proof and any assertion that BTA conditions precedent
have been fulfilled.

Outputs explicitly retain original_pdf_verified=false,
actual_conversion_pricing_verified=false, transfer_completed=false,
expected_return=false, capital_eligibility=false and no target price.

## Mandatory next evidence

- Independently retrieve and hash the exact original 7 October filing
  and Annexure A/B, including inter-company deposit rate, collateral,
  subordination, conversion terms and third-party rights.
- Obtain the executed BTA conditions precedent and subsequent
  listed-company closure/effective-date notice.
- Obtain audited WWIL O&M carve-out FY26 EBITDA, maintenance capex,
  receivables, working-capital needs, contracted renewal and
  standalone/free-cash-flow data.
- Verify final VEPL shareholder register/share classes, consolidated
  minority interests and complete Inox Green post-QIP fully diluted
  ordinary shares and net cash/debt.
- Re-run an **independently frozen** downside/upside valuation bridge
  only after the above documents clear and appropriate time/date
  controls are respected.

**Portfolio eligibility and live capital remain disabled.**
