# CC001 P014: separate event facts and a usable assisted-review path

## Product decision

P011/P012 showed that the tested small models are not reliable enough to populate
accepted investment facts. P013 exposed omissions but did not fix their answers.
This change does not run another small-model comparison. It implements a usable
explicit assisted-review path with independent fields, rather than blocking all
research on autonomous-model quality or pretending that new diagnostics solve it.

An order recipient can be a consortium while the disclosed amount is issuer scope.
Signing, incorporation, completion, payment and operations are not successive
aliases of one stage. A credit grade and credit outlook are separate. Required
questions must be addressed, with [] explicitly meaning unknown. No missing field
is silently interpreted as a negative answer or completed transaction.

## Executable data contract

`company_change_event_facts` binds one event to an exact source URL, symbol, ISIN,
original-file hash and extracted-text hash. Its observations are typed assertions
with exact source spans. A source statement is preserved even when it conflicts
with another. A single distinct value is a REVIEWED_ASSERTION, no values is UNKNOWN,
and multiple distinct values is CONFLICT. There is no majority vote, most-optimistic
selection, or automatic implication from signing to payment or operating revenue.

Named local review attestation is required to import a package. This is assisted
research, not authenticated independent review or an entailment evaluator. The
reviewer can still misinterpret a valid passage. A valid source span and typed
schema do not prove semantic accuracy. No model response is automatically admitted.

Each category has its own questions. Order recipients, acquisition investors and
credit obligors are not placed into one ambiguous actor field. Amount ownership is
attached separately to each monetary item, not inherited from the event recipient.
Compatible amount qualifiers, such as an upper limit and payment in tranches,
coexist without being misrepresented as conflicting alternatives.

Source money is parsed with Decimal using its original currency and unit. No FX is
silently applied. The source amounts in the assisted development package are:

- SEAMEC: USD 26.14 million for the issuer's own scope, excluding GST.
- Dhruv: INR 3,025,000, or 0.3025 crore, of subscribed consideration.
- Prestige: up to INR 5,237.6 million, or 523.76 crore, payable in tranches.

The last two are consideration obligations, not revenue or collected cash.

## Persistence and corrections

The only new database table is `cc_event_fact_reviews`. Imports validate the whole
package before atomic insertion. Repeating the same package/reviewer is idempotent.
Original source blobs, financial extractions, prior news reviews and trading records
are not changed. Export rechecks the original capture, text and record hashes.

Multiple reviews of the SAME source/event accumulate assertions. Repeating an
optimistic review cannot erase a contradictory source claim. Different events or
source revisions are not merged silently. Explicit correction/retraction and
cross-document supersession are not implemented by this additive source ledger.
A new filing remains a separate source record pending review of what it supersedes.
Historical exports use their observation cutoff and cannot see later attestations.

## Conditional economics, not investment approval

The fact desk connects admitted source facts to existing dated company/price
context and the finite-contract cash function. A hypothetical order scenario
requires an uncontested award and an uncontested contract amount and owner.
Conflicted events, unsupported categories and unknown amount ownership are blocked.
An amount explicitly owned by the issuer cannot be scaled by consortium ownership
a second time. Hypothetical FX, cash margin, baseline inclusion, funding and receipt
timing remain separate inputs. There is no terminal value or inferred share count.

Payment and operating unknowns remain visible even when a hypothetical award case
is calculated. The calculation does not book revenue, profit, cash or a trade.
A pre-event price remains a reference, not a fill after research was available.
The distinction between a contract and revenue recognition is consistent with
IFRS 15's performance-obligation principle, but this tool is not accounting advice.

`company_change_fact_desk` exports JSON and a self-contained searchable HTML desk.
It shows the fields, contradictory evidence, unknowns, amounts, dated price,
research action and next decisive checks together. A blocked scenario does not
cause the original source to disappear from the report.

```bash
python -m marketlab.company_change_fact_desk \
  --workspace .marketlab/cc001 \
  --package data/fixtures/company_change_fact_reviews.json \
  --reviewer assistant-source-review-seen-development \
  --plans data/fixtures/company_change_fact_scenarios.json \
  --output-prefix .marketlab/exports/reviewed-event-facts
```

Omit `--package` and `--reviewer` to export already admitted reviews only. The
fixture refers to four exact, previously inspected originals. It is a seen
assistant-authored development package, not a blind model benchmark. Using it
requires the matching retained source readings. The isolated source workflow
retrieves those originals and provides this full replay without operator guesswork.

## Actual development implications

SEAMEC remains a consortium award with issuer-specific value. Completion is pending
and commencement is unconfirmed. Signing, payment and baseline inclusion are not
established by the cited clauses. Conditional finite-order scenarios are allowed,
not a realized-earnings update or a stock purchase.

Dhruv's subsidiary is incorporated, not operating. Its paid-versus-unpaid statements
remain conflicted, and the underlying award was previously disclosed. The research
action is source reconciliation, not treating the incorporation as a fresh order.

Vikran's existing grade is reaffirmed while its outlook is negative. Funding pressure
is reported and liquidity improvement is expected, not established cash receipt.
The new proposed-debenture issue is not conflated with the existing-facility event.

Prestige's agreement is signed, completion is conflicted and consideration is payable.
The presence of a signed agreement does not resolve the completion contradiction.

## Verification boundaries

Unit tests cover exact source binding, atomic/idempotent imports, unknowns,
contradiction retention across reviews, amount ownership and units, event isolation,
future observations, corruption, schema bounds, blocked scenarios and safe HTML.
The original-source smoke restores a copy of cc001-state, revalidates the four
filings, explicitly admits the assisted package and produces four dossiers with
two conflicts and seven hypothetical cash cases. It verifies unchanged financial
and prior review table counts. No provider inference occurs.

The smoke has read-only repository permission and cannot push production state.
Existing daily budgets, schedules, model release gates and frozen H/HG/AE
experiments remain unchanged. This completes the assisted fact-to-economics path,
not autonomous interpretation, independent accuracy, prospective stock-selection
performance, source-wide coverage or commercial rights/hosting.

Primary design references, not claimed as reproduced evaluations:
- Min et al., FActScore, atomic claim evaluation: https://aclanthology.org/2023.emnlp-main.741/
- IFRS 15, performance obligations: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/
