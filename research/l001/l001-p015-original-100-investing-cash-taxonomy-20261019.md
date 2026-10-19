# L001 P015 | Original 100-company cash-investing taxonomy

**Research date:** 19 October 2026. **Status:** audited original XBRL accounting *source analysis*, not pre-October-15 alpha. All capital disabled.

The project objective is economically sustainable shareholder cash flows, not a visually attractive CFO minus PPE screen. L001 P014 demonstrated a major challenge: Sun TV FY26 cash from operations ₹1,801.64 crore less cash PPE ₹83.91 crore looks like positive ₹1,717.73 crore. Original source **intangible asset purchases ₹2,130.31 crore** reverse the proxy to **negative ₹412.58 crore**. The franchise-rights acquisition may be nonrecurring growth spending, but that is not yet reconciled with the cash-flow line. Neither proxy should be treated as owner earnings.

## Concrete scope

Reread the exact source-frozen **100 annual FY26 XBRL original documents** in L001 P004 GitHub Actions artifact 12111414537, P004 source SHA 97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d. Source publication must precede the original October 15 source cutoff.

Inventory every genuine investing cash-flow concept with exact annual context FourD and INR unit, including gross PPE, intangible purchases, business/investment acquisition, proceeds and net investing aggregates. Keep each original concept/value, exact source SHA, symbol, ISIN, accounting scope and publication time. Reject conflicting duplicates, wrong fiscal context, nonfinite cash amounts and altered original bytes.

**Do not sum cash investing taxonomy rows.** Cash-flow aggregations may contain gross components, net proceeds, investment purchases and overlapping notes, which otherwise double-count cash. Missing tags are *unknown economic coverage*, not evidence of zero expenditure. Specifically: the absence of a standard intangible purchase tag does not prove the issuer has no franchise, software, R&D, media-content or licensing spending elsewhere.

For each company separately report: reported CFO, original PPE purchase cash, original intangible purchase cash, CFO minus both spending categories as an explicitly nonnormalized category proxy, individual original investing source concepts and descriptive flags for further review. This is **not** a value model or comparison of unrelated accounting regimes, and does not remove any of the original 100 companies.

## Temporal and causal limits

All interpretations here are **post-hoc October 19 research**. Although the original FY26 exchange filings predate October 15, the research method was not frozen before the HG009 observation window and cannot be retroactively entered as a prediction. Likewise, the presence of net investing cash and source concept tags does not show whether outflows are *recurring maintenance* versus opportunistic asset purchases or acquisitions.

The next underwriting gate is issuer-specific bank/cash settlement and investing-note reconciliation. Sun TV in particular needs to tie its franchise purchase to the audited intangible investing line rather than simply adding back a management transaction. Valuation can follow only when actual multi-year sustaining reinvestment, parent share of cash, liabilities, fully diluted shares and a dated executable-price basis are independently verified.

**No stock expected returns, fair values, security rankings or live capital authorization from this taxonomy.**

Reproduce with source-pinned CLI scripts/materialize_l001_p015_investing.py and tests/test_l001_p015_investing_taxonomy.py. Original P004/P014 source digest, first publication clock and 100-name denominator must always remain intact.


## Revision after all-100 original source replay: exclude zero-valued taxonomy boilerplate

The first original 100-company replay revealed a source-format trap: the annual XBRL templates expose about 28 investing cash concepts for essentially every company, including many exact **zero** financial cash cells. Counting those present-but-zero concepts as 100 companies with new transactions would be misleading. P015 therefore preserves every exact original item while distinguishing **nonzero actual statement amounts** from zero-valued template cells and listing separately only nonzero investing components that require primary-note review.

This exposes concrete *reported cash-classification* questions, not new share return predictions:

- **ACE:** FY26 CFO ₹417.27cr and PPE ₹93.26cr produce earlier ₹324.01cr CFO-minus-PPE. Separately, original FY26 tagged cash payments for acquisition of other entities' equity/debt instruments **₹831.07cr**, receipts from their sale **₹508.32cr**, and net cash investing **−₹349.89cr**. These financial-asset movements are not necessarily maintenance capex; the issuer note must resolve unrestricted investments and shareholder available cash.
- **MAYURUNIQ:** reported source purchases of other long-term assets **₹266.2441cr** and corresponding disposal/proceeds **₹160.3842cr**, versus earlier FY26 CFO-minus-PPE **₹108.9456cr**. Their label is insufficient to infer recurring asset maintenance or exact cash availability. Avoid attributing a gross amount to owner FCF without original asset/investment notes.
- **OIL:** original source CFO **₹10,683.75cr**, standard PPE purchase tag **zero**, and net investing cash **−₹10,381.37cr**, including other investing category **−₹11,396.33cr**. This is a decisive *taxonomy mismatch* for the industrial CFO-minus-PPE framework, **not** evidence that the company had zero productive capital spending.
- **SUNTV:** FY26 intangible cash **₹2,130.31cr**, source net investing **−₹1,311.46cr**. This illustrates why simultaneously subtracting gross intangible purchases and aggregate net investing would double count financial flows.

Original cash tags can themselves be signed unexpectedly, even for items labelled cash proceeds. **Do not infer economic direction from the English local tag name alone**. Reconciliation with cash-flow note conventions and changes in investments/deposits is a separate next step. These discoveries remain dated FY26 historical facts interpreted October 19, not pre-registered October 15 alpha.


## Independently reproduced all-100 result, October 19

The revised original-source replay passed CI, revalidated the same **100 annual XML files**, and sealed the complete P015 report under SHA-256 **fcceac6870ee20ce238448e9926b317e10c6d859257f43839726b0c9a076cfdd**.

- 96 companies have a **nonzero** standard PPE purchase cash tag, four have the exact reported tag zero. Zero is not a guarantee of no capital investment.
- 17 have **nonzero** standard intangible asset purchase cash tags, consistent with P014. The other 83 zeros are not guarantees of no license, content, intellectual-property or business acquisitions.
- **36 of 100** have at least one *positive additional investing-purchase classification tag* that exceeds the absolute CFO-minus-PPE cash proxy. This is a documentation/normalization review indicator, **not proof of incremental maintenance spending or positive/negative alpha**. Investment securities transactions in particular can create very large purchase and sale gross legs that are inappropriate to subtract as recurrent owner cash.
- **55 of 100** have the absolute value of the tagged net investing cash flow larger than their crude CFO-minus-PPE proxy. This confirms a general *classification gap* that must be investigated by source, but net investing includes proceeds, acquisitions and timing, so it cannot simply be substituted for capex.
- All 100 have at least one additional **nonzero investing source tag** beyond standard PPE, intangibles and net investing. This is not a discriminating screening feature by itself. Source tag count, zero-template presence and company return expectation remain entirely separate.

The material-purchase review cases include ACE, MAYURUNIQ, SUNTV, TRAVELFOOD, selected banks/NBFCs and other industrial/media businesses. These are **not stock-buy priorities by mechanical count**. The same archived source should be classified by accounting regime and then reconciled against the audited issuer notes before any cash flow is labeled sustaining.

**All original 100 member identities preserved, no retrospective forecasts, zero company expected-return estimates or capital permissions.**
