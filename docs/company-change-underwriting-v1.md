# CC001 P006: cash conversion, balance-sheet evidence and entry-input contracts

This release addresses a concrete economic weakness in P005: an improving
revenue/PBT quarter can coexist with cash consumption or debt-funded expansion.
It rereads the retained original XBRL, not the previous income-only fact set.
No model endpoint, paid feed, trade permission or frozen experiment is changed.

## Implemented

`company_change_financials` extracts same-issuer, same-scope undimensioned
income/cash-flow durations and balance-sheet instants. Exact source concepts,
context IDs, original literals, units, byte hashes and rounding accuracy survive.
Namespace-qualified currency units and entity identities must match. Conflicting
values, ambiguous contexts, malformed units and unsupported source layouts fail
rather than being repaired. Display rounding never multiplies raw instance values.

`company_change_underwriting` joins cash and profit for the EXACT same period.
It compares operating cash with group PAT, not group cash with parent-only PAT.
The capex diagnostic includes explicitly disclosed PPE purchases, intangible
purchases and intangible development. All three are required, with nonnegative
outflow conventions. Missing fields are not zero and negative payments are not
silently made positive. This is not maintenance capex or owner free cash flow.
Other investment, acquisition, lease and financing-interest facts are retained
separately rather than quietly mixed into operating cash.

Gross borrowings require both current/noncurrent components or a supported
explicit total. Reported cash equivalents alone are offset. Other bank balances
and investments are NOT assumed unrestricted. The resulting measure is named
`net_borrowings_excluding_leases`, not total enterprise net debt. Unclassified
lease obligations and cash restrictions remain decision gaps. A current ratio
is displayed as a diagnostic, not a sector-adjusted bank/NBFC solvency score.

## Reconciliation is part of the financial result

Checks include owner plus minority PAT against group PAT, assets against equity
plus liabilities, opening cash plus operating/investing/financing/FX flows against
closing cash, and the cash-flow statement's cash against balance-sheet cash.
Tolerance is derived from the XBRL `decimals` accuracy of each input, not a magic
absolute threshold. Unknown accuracy remains explicitly unknown. A difference
can be legitimate cash-definition/overdraft policy, not necessarily bad accounts.
The system asks for reconciliation. It does not accuse the issuer or rewrite data.

Newly parsed cash/debt facts remain UNREVIEWED even when an older income-only
extraction was accepted. An old acceptance is not inherited by new metrics.
Parsing time is recorded now. Historical capture time is never reused as if this
new analysis had existed earlier. Source blobs and original extraction records
are not modified.

## Year-ago and valuation boundaries

Exact same-source year-ago comparisons are computed when available. Otherwise
the report names the missing start/end dates. It does not turn a sequential jump
into a year-over-year improvement or assert that seasonality has been solved.
Cross-document/restated comparability still needs source-specific review.

The optional `entry_sensitivity` interface bridges source-backed ANNUAL owner
PAT to the existing CC001 valuation function. It requires an explicit signed,
after-tax owner-normalization adjustment, a fully diluted share count, exact
quoted evidence, reviewer identity, review time, period/issuer/scope binding and
capital-event checks through the quote date. Zero adjustment is an affirmative
review input, not the default for missing notes. Half-year results cannot be
annualized. Stale/future quotes remain subject to the existing valuation gates.

This is an analyst-attested scenario contract, not independently certified
intrinsic value or a recommendation engine. The code does not infer dilution
from rounded share capital or reported EPS. No real valuation case was invented
for the retained source sample. No probability of a multibagger is assigned.

## Run

```bash
python -m marketlab.company_change_underwriting \
  --workspace .marketlab/cc001 \
  --output-prefix .marketlab/cc001-exports/cash-underwriting
pytest -q tests/test_company_change_underwriting.py
```

The command writes a latest-view HTML/JSON pair and content-addressed copies.
Failures remain visible in the denominator and return nonzero. The output
records its input snapshot hash, new implementation hash and evaluation time.
Optional `--entry-cases` accepts populated analyst evidence, not future-return
labels. Its format is exercised end-to-end by the synthetic `annual_case` test.

The existing daily workflow generates the cash report after reported-business
comparisons. Even a financial-export failure cannot prevent the original data
checkpoint or state push. The latest-state metadata marks the cash export FAILED
and clears its current counts/hash in that case. Old dated files are not current
successes. Schedule cadence and the 40-document acquisition cap do not change.

## Evidence produced during development

The frozen input was the actual checkpoint from run 42370417056. Its original
ZIP SHA was d578766b2efe947c7d7c633788cb46087fa86b3dbf1aa510cd679ff71ee8bbf6.
Every one of its 155 checkpoint members passed hash verification and SQLite
integrity_check returned ok before analysis. Source-derived assertions were not
substituted for the retained XML bytes.

The development replay covers 113 scope-specific cards for 67 issuers. No later
market outcomes were consulted. These are selected operational backlog inputs,
not independent labels or a representative performance sample. Software tests
and source-arithmetic checks do not establish general extraction accuracy or
investment alpha. Actual CI and merged daily-run status must be reported separately.

## Design references

- XBRL International, XBRL 2.1 specification, contextRef/unitRef and numeric accuracy:
  https://www.xbrl.org/specification/xbrl-2.1/rec-2003-12-31/xbrl-2.1-rec-2003-12-31+corrected-errata-2013-02-20.html
- IFRS Foundation, IAS 7 overview, operating/investing/financing and cash reconciliation:
  https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/

The program interprets the actual issuer's NSE taxonomy concepts. These references
explain the accounting separation, not a legal certification of Ind-AS compliance.
