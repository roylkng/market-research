# CC001 P010: semantic execution and finite event economics

## End-to-end path

Original announcement -> bounded structured proposal -> source-span validation
-> explicitly attributed review -> company identity/financial-context join
-> publication-aware price check -> finite event cash scenarios.

The new components reuse the existing byte store, evidence reviews, company
context, configured-model policy and SQLite workspace. They do not create a
parallel forecast platform or modify frozen H-series, HG009 or AE001 experiments.

## Model worker

`company_change_semantics` prepares exact requests by default. To actually use an
operator-approved endpoint, the existing CC001_MODEL_URL/CC001_MODEL_NAME and
optional CC001_MODEL_API_KEY configuration is required, along with explicit
`--execute`. The pre-existing HTTPS/explicit-loopback policy applies. JSON-schema
chat completions are supported by compatible local servers such as vLLM.

Each request is reserved durably before network execution. Repeating the identical
request reuses the prior attempt, including failed or interrupted attempts. No
automatic paid retries, schema-repair calls, external tools or broker actions
occur. The CLI bounds calls to 1..20, requests an output-token cap, enforces an
80,000-character source limit and a two-MiB response limit. Character bounds and
provider-reported token usage are not guarantees of billing cost. An operator
must approve the configured provider and its rates before execution.

Model claims use exact unique source quotes. Offsets and source identity are
computed by the client rather than trusted from the model. Refusal, truncation,
tool calls, fabricated/ambiguous quotes, duplicate events and schema violations
are recorded as failures. Arbitrary transport text and credentials are not logged.
Raw request/response bytes and actual observation clocks are retained.

A valid response is MODEL_PROPOSED_NOT_APPROVED. It does not create an accepted
source review, verified event, accounting fact or investment decision. The existing
explicit `company_change_news_review` path is the only supported review admission.
Syntactically valid quoted text does not prove a semantically correct reading.

The worker includes category/stage/actor evaluation against separately supplied
labels. Missing documents, failures and abstentions remain in the recall denominator.
Metric scope and label provenance are explicit. Software does not certify that
labels are independent, and this is not a return-prediction evaluation.

## Event economics

`company_change_event_bridge` verifies retained review and company-context hashes,
rechecks original quotation/capture evidence, and joins only identical symbol/ISIN.
Consolidated context is preferred explicitly when both scopes are available.
Unreviewed proposals cannot silently enter this path. Production reviews are not
created from the development fixture.

The event clock distinguishes public disclosure time from when this system had
read and reviewed the evidence. A price before publication is PRE_EVENT_REFERENCE.
A same-day date-only close cannot prove it follows publication. A price observed
after publication but before this system's review is not a prospective fill.
Even a later dated close is not evidence of executable trading liquidity.

The current calculation handles a finite awarded or signed order, not acquisitions,
capacity announcements, credit events or cancelled/unresolved proposals. Source
amounts are tied to a reviewed quotation with explicit currency and unit. An
issuer-specific award cannot be multiplied by its participation fraction a second
time. Total-consortium allocations require a separately declared fraction.

All cash assumptions are explicit: FX, fraction not already included in the base
case, after-tax cash margin, additional investment, working-capital funding and
recovery, collection timing and discount rate. None is extracted from the order
headline or represented as an estimated probability.

    incremental_contract = source_amount * FX * issuer_fraction * incremental_fraction
    cash_surplus = incremental_contract * after_tax_cash_margin
    finite_NPV = -capex - working_capital
                 + (cash_surplus + recovered_working_capital) / (1+r)^(months/12)

This simplified scenario puts funding at time zero and net receipts at the supplied
time. It is not a detailed milestone model or an accounting revenue-recognition
schedule. It has **no terminal value and no P/E multiplier**. One contract is not
perpetual earnings. Unverified shares cannot generate a per-share value. A contract
already fully included in the base case creates no new incremental receipts.
Loss-making cases and unrecovered working capital can reduce value.

## Executable interfaces

```bash
python -m marketlab.company_change_semantics --workspace .marketlab/cc001 \
  --limit 4 --output .marketlab/cc001-exports/semantic-preparation.json

python -m marketlab.company_change_event_bridge --workspace .marketlab/cc001 \
  --output-prefix .marketlab/cc001-exports/event-economics
```

The first command performs no external inference. Approved operator execution
adds `--execute` after actual endpoint configuration. The second uses retained
explicit event reviews. An optional `--plans` supplies source-bound hypothetical
cash scenarios. All results retain live_capital_allowed=false.

The read-only original-source verification restores a copy of saved state, rereads
four previously inspected disclosures, admits them as **seen development reviews**,
prepares model requests without calling a model, captures actual SEAMEC financial
context and calculates the explicit finite-order sensitivities. It preserves all
original evidence and exact implementation bytes for replay. These four cases are
not a blind test set and no live model accuracy is claimed.

## SEAMEC development case and its limits

The reviewed source amount is USD 26.14 million for the issuer's own work scope.
The fixture's INR 85/USD conversion is hypothetical, not an observed exchange rate.
Five, ten and fifteen percent cash-margin scenarios, a twelve-month receipt,
fifteen-percent discounting and zero new investment are assumptions, not forecasts.
Other cases show prior baseline inclusion and financing/investment drag.

The previously retained 6 November 2026 close precedes the public award filing.
It must not be treated as a post-news entry. Current exceptional gains, sustainable
owner earnings, execution capacity, incremental costs, fully diluted shares and
post-disclosure price still require evidence. The finite-order scenarios cannot
justify adding an earnings multiple to the whole award value.

## Completion boundaries

Implemented: original-document intake, persistent financial history, financial
and cash checks, dated market context, source-bound announcement reviews, an
opt-in semantic model runner, classification scoring, and event-to-economics join.

Not demonstrated by these changes: a configured live inference service, independent
semantic accuracy, normalized owner-earnings cases for the full universe, sustained
market-wide service, predictive outperformance or commercial readiness. Those
require actual provider/runtime configuration, independent labels, prospective
outcomes, approved storage/data rights and deployment. Software tests do not
substitute for these. No secret, paid model account or commercial service was
provisioned. No current operator permissions or investment gates were relaxed.

Primary design references:
- vLLM structured outputs: https://docs.vllm.ai/en/latest/features/structured_outputs/
- IFRS 15 revenue from contracts with customers: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/
