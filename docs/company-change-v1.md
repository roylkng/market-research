# CC001: company changes to research decisions

Status: implemented offline research prototype. Live capital disabled.

CC001 adds a bounded disclosure-to-decision path. It is not another prediction
framework, a trained return model, an investment recommendation service, or an
alternative version of any frozen experiment. No existing H-series, HG009,
AE001, source schedules, selection cohorts, or outcome ledgers are modified.

## Run

From the repository root with the existing development environment:

```bash
python -m marketlab.company_change data/fixtures/company_change_v1.json \
  --out .marketlab/company-change
pytest -q tests/test_company_change.py
```

Without installing the package, prefix the first command with `PYTHONPATH=src`.
The command prints exact paths to a content-addressed JSON report and a static
HTML company-change inbox. Repeating identical input is idempotent. Changed
input produces a new artifact rather than overwriting the old decision.

The bundled fixture is entirely synthetic. It contains no historical stock
selection, real recommendation, licensed news, or claimed investment outcome.
The demonstration includes six source events, one duplicate, one linked state
revision, one future disclosure excluded at the cutoff, and three decision
cards: review candidate, pass at this price, and wait. All three are visibly
DEVELOPMENT_ONLY because their evidence is synthetic.

## Implemented path

```
Existing canonical NSE announcement + recorded source text
                  |
         identity, clocks, rights, text hash
                  |
      explicit labels OR cited model proposals
                  |
      typed facts + duplicate/revision reconciliation
                  |
      earnings / finite contract / equity issuance bridge
                  |
      unweighted valuation sensitivity + decisive unknowns
                  |
           immutable JSON + readable HTML
```

There are no new dependencies. The implementation is a standalone module under
`src/marketlab/company_change.py`, runnable without changing the existing large
CLI or experiment modules.

### Existing acquisition integration

`from_nse_announcement()` accepts the existing
`alpha_announcements.canonical_announcement()` output. It verifies the existing
canonical announcement hash and retains its symbol, source URL and publication
clock. The caller must supply ISIN, source rights, scope, reporting period,
event lineage, evidence mode, first observation, and text-recording timestamps.
Those facts cannot be inferred from a news headline.

This is a read-only adapter, not a new downloader or a claim that a production
collector has already been scheduled to feed CC001. Keep acquisition and raw
original-document custody in the existing collector.

### Two extraction interfaces

1. The deterministic baseline reads explicit label-value lines. It rejects
   missing units, foreign currencies, repeated labels, invalid numbers, and
   unsupported stages. It does not guess PDF column alignment or normalize
   arbitrary prose into facts.
2. The provider-neutral interface accepts `proposed_facts` from an LLM or a
   reviewer. Each fact requires exact character offsets, source quote, and a
   literal that is present in that quote. The numeric literal must retain its
   currency and units. Hallucinated or mutated passages fail validation.

Generate model requests without making an API call or spending API credits:

```bash
python -m marketlab.company_change data/fixtures/company_change_v1.json \
  --out .marketlab/company-change-prompts --extract-prompts
```

The generated JSON includes `extraction_requests`. `extraction_request()` also
returns a request directly for any configured model adapter. The provided text
is explicitly treated as untrusted data. The adapter has no tool or trade
permissions. An actual inference endpoint is not connected by this change.

Attach a model result to the original source as:

```json
{
  "proposed_facts": {
    "revenue": {
      "start": 0,
      "end": 40,
      "quote": "Revenue from operations: INR 1,200 crore",
      "literal": "INR 1,200 crore"
    }
  },
  "proposed_facts_at": "2026-11-07T10:00:00+05:30"
}
```

Offsets in this example refer to exactly the displayed 40-character text,
not to the longer demo fixture. Model extraction has its own timestamp. A
later extraction or review cannot become an earlier decision's information.

Matching a quote does not prove that a number is the right period, accounting
scope, or economic concept. Model proposals are therefore not eligible for a
review-candidate card until semantic review is recorded through `reviewed_by`
and `reviewed_at`. These fields are caller attestations, not a secure approval
system. This is an integration boundary, not a claim of autonomous understanding.

## Financial bridges

| Lane | Supported in v1 | Explicit limits |
|---|---|---|
| Earnings quality | Revenue comparison, symmetric after-tax owner-PAT adjustments, normalized owner EPS, CFO less plant/intangible cash spend | Prior periods must be comparable. CFO less capex is not parent owner cash. Missing exceptions are not zero. |
| Operational inflection | Finite contract revenue spread over execution years, incrementality, margin, tax, ownership, maintenance spend and initial working capital | Equal execution is a scenario. Initial working capital is not deducted every year. Nothing is added to recognized earnings. No perpetual capitalization. |
| Capital allocation | Proposed/completed share issuance, gross proceeds, dilution and unchanged-profit EPS factor | Not a buyback/acquisition model. Gross proceeds are not earnings. Only completion updates effective shares. |

All monetary statement values normalize to INR crore. Shares remain share
counts. EPS and prices remain INR per share. Calculations expose their inputs.
Consolidated and standalone lineages never merge. Identity uses symbol and ISIN.

## Company-state rules

State is reconstructed deterministically from the supplied bundle, ordered by
when information became available. Identical facts within a supplied event
lineage are duplicates. Changed facts require an explicit `supersedes` link to
the active source. Revisions preserve the old event and expose changed fields.
This is not yet a persistent cross-batch database or automatic entity linker.
The caller supplies the event key. Cross-key semantic deduplication is not
claimed. A repeat with a stronger source authority currently remains a repeat
rather than automatically upgrading the first source's authority.

## Decision policy

A card uses an annual, normalized owner-EPS baseline and explicit bear/base/bull
assumptions for earnings growth, annual share dilution, and exit P/E:

```
terminal_price = owner_eps * ((1 + earnings_growth) / (1 + share_dilution))**years * exit_pe
net_price_multiple = terminal_price * (1 - exit_cost) / (entry_price * (1 + entry_cost))
price_cagr = net_price_multiple**(1 / years) - 1
base_hurdle_entry = base_terminal * (1 - exit_cost) / ((1 + hurdle)**years * (1 + entry_cost))
```

No scenario receives an invented probability. The model does not estimate
intrinsic value independently of its assumptions. Dividends and investor taxes
are excluded. Cost inputs are assumptions, not observed execution spreads.
Bear terminal loss is not maximum path drawdown. Uncertain treasury cash is
excluded instead of assumed unrestricted and added to equity value.

- REVIEW_CANDIDATE means the supplied base hurdle and bear terminal-loss bound
  pass with no explicitly unresolved material unknown. It means analyst review,
  not investment approval, suitability, portfolio inclusion, or a trade.
- PASS_AT_THIS_PRICE means the stated assumptions do not clear that policy.
- WAIT means a decisive unknown, stale quote, interim/nonpositive/unknown EPS,
  later issuance, missing invalidation condition, or unreviewed model extraction
  prevents a complete comparison.
- Synthetic, reconstructed and secondary-source cards remain DEVELOPMENT_ONLY,
  retaining the illustrative disposition for development testing.

Quotes older than seven calendar days and annual earnings older than 550 days
are blocked by explicit prototype policy. These are engineering defaults, not
learned thresholds or empirically optimal investment rules.

## Safety and provenance boundaries

Information availability is the latest of publication, first observation, text
recording, model extraction, and semantic review. Future documents are deferred.
A hash identifies the supplied UTF-8 text. It is NOT an assertion that original
PDF bytes have been archived or that source authenticity has been established.

Source usage rights are recorded separately. UNVERIFIED use is rejected.
Commercial output requires every source to be marked REDISTRIBUTABLE. A caller's
rights flag does not create a license or discharge legal obligations.

There is no network call, credential requirement, live execution, scheduling,
model training, investor-personalization logic, or public service deployment.
HTML source text is escaped. Output writing refuses frozen experiment
namespaces and mismatched existing artifacts. No canonical experiment state is
read for tuning or written by the module.

## Completed checks and remaining work

The companion tests exercise all three financial bridges, Indian/international
numeric units, five distinct information clocks, duplicate/revision lineage,
source hashes, rights, citation offsets, review gates, currency/scope boundaries,
valuation costs/dilution, unsafe HTML, artifact replay, protected namespaces,
the existing NSE canonical-row adapter, and the command-line path.

Next implementation work is a real-source, separately labeled development
corpus and a configured extraction adapter. Its semantic precision must be
measured against human-reviewed labels before unattended use. Persistent
cross-batch state, broader event types, statement-table extraction, provider
licensing, multi-tenant controls and commercial validation are not implemented.

The later controlled A/B/C test remains separate from this release: numerical
baseline, baseline plus sentiment, and baseline plus verified economic changes.
Use the existing evaluator, identical decision/execution clocks and costs, a
new trial record, and prospective frozen predictions. No existing frozen
hypothesis may be modified or retrospectively improved. No predictive edge is
established by passing these software tests.
